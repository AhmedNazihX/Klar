"""The user data the screens need (supabase/migrations/*_user_data_screens.sql, story P19): the
company profile and its size class, run numbers and inputs, duty progress, my_data_counts(), the
export-import round trip and the cleanup.

The helpers come from test_user_data_schema.py, which also covers the new table in its per-table
tests (RLS, timestamps, delete my data, the storage measure and the cleanup's cascade).
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, LiteralString
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.db.conftest import _database_url
from tests.db.test_user_data_schema import (
    LOCK_WAIT_SECONDS,
    STORAGE_BUDGET,
    USER_TABLES,
    _add_classification,
    _add_system,
    _committed_user,
    _counts,
    _create_user,
    _on,
    _one,
    _pid,
    _purge,
    _usage,
    _user_exists,
    _wait_until_blocked,
    as_user,
)

pytestmark = pytest.mark.db

PROFILE = {
    "company_name": "Nordwerk Logistik GmbH",
    "staff_band": "10-49",
    "turnover_band": "up_to_10m",
    "established_in": "DE",
    "used_in": "eu",
}
INPUTS = {"description": "Ranks job applicants.", "answers": {"eu_use": "yes"}}

ADD_RUN = """
    insert into classifications (system_id, risk_class, status, law_version, result, inputs)
    values (%s, 'high_risk', 'decided', 'amended', '{}', %s) returning run_no
"""


def _set_profile(db: psycopg.Connection, inventory: UUID, profile: dict[str, Any]) -> None:
    """As the current user: fill in the inventory's company profile."""
    db.execute(
        """
        update inventories set company_name = %(company_name)s, staff_band = %(staff_band)s,
          turnover_band = %(turnover_band)s, established_in = %(established_in)s,
          used_in = %(used_in)s
        where id = %(id)s
        """,
        {**profile, "id": inventory},
    )


def _add_run(db: psycopg.Connection, system: UUID, inputs: dict[str, Any] | None = None) -> int:
    """As the current user: a classification of `system`; returns its run_no."""
    return _one(db, ADD_RUN, (system, None if inputs is None else Jsonb(inputs)))


TURNOVER_BANDS = ("up_to_10m", "up_to_50m", "up_to_150m", "over_150m")
SIZE_CLASSES = {
    "1-9": ("sme", "sme", "smc", "none"),
    "10-49": ("sme", "sme", "smc", "none"),
    "50-249": ("sme", "sme", "smc", "none"),
    "250-749": ("smc", "smc", "smc", "none"),
    "750+": ("none", "none", "none", "none"),
}
"""The size class per staff band, for each turnover band in TURNOVER_BANDS order: an SME has under
250 staff and up to EUR 50 m turnover; a small mid-cap is otherwise under 750 staff and up to
EUR 150 m (decision 026 item 22)."""


@pytest.mark.parametrize(
    ("staff_band", "turnover_band", "size_class"),
    [
        *(
            (staff, turnover, size_class)
            for staff, classes in SIZE_CLASSES.items()
            for turnover, size_class in zip(TURNOVER_BANDS, classes, strict=True)
        ),
        (None, "up_to_10m", None),
        ("1-9", None, None),
        (None, None, None),
    ],
)
def test_the_size_class_follows_the_bands(
    db: psycopg.Connection,
    staff_band: str | None,
    turnover_band: str | None,
    size_class: str | None,
) -> None:
    user = _create_user(db)
    with as_user(db, user):
        derived = _one(
            db,
            "insert into inventories (name, staff_band, turnover_band) values ('Acme', %s, %s)"
            " returning size_class",
            (staff_band, turnover_band),
        )
    assert derived == size_class


def test_the_size_class_is_derived_never_written(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        inventory = _add_system(db)["inventories"]
        _set_profile(db, inventory, PROFILE)
        assert _one(db, "select size_class from inventories") == "sme"
        changed = _one(db, "update inventories set staff_band = '750+' returning size_class")
        assert changed == "none"
        with pytest.raises(psycopg.errors.GeneratedAlways), db.transaction():
            db.execute("update inventories set size_class = 'sme'")


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("company_name", ""),
        ("staff_band", "250+"),
        ("turnover_band", "up_to_5m"),
        ("established_in", "Germany"),
        ("established_in", "de"),
        ("used_in", "worldwide"),
    ],
)
def test_profile_fields_take_only_the_listed_values(
    db: psycopg.Connection, column: str, value: str
) -> None:
    user = _create_user(db)
    with as_user(db, user):
        inventory = _add_system(db)["inventories"]
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(_on("update inventories set {} = %s", column), (value,))
        _set_profile(db, inventory, PROFILE)


def test_user_b_cannot_read_or_change_user_a_profile_runs_or_ticks(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        rows = _add_system(db)
        _set_profile(db, rows["inventories"], PROFILE)
        _add_run(db, rows["systems"], INPUTS)
    with as_user(db, user_b):
        assert db.execute("select company_name, size_class from inventories").fetchall() == []
        assert db.execute("select run_no, inputs from classifications").fetchall() == []
        assert db.execute("select obligation_key, created_at from duty_progress").fetchall() == []
        assert db.execute("update inventories set staff_band = '750+'").rowcount == 0
        assert db.execute("delete from duty_progress").rowcount == 0
    with as_user(db, user_a):
        assert _one(db, "select size_class from inventories") == "sme"
        assert _one(db, "select inputs from classifications where run_no = 2") == INPUTS
        assert _one(db, "select count(*) from duty_progress") == 1


UNDER_A_SYSTEM = {
    "matching": (
        "insert into classifications (system_id, risk_class, status, law_version, result)"
        " values (%s, 'high_risk', 'decided', 'amended', '{}')",  # B's run 1, like A's
        "insert into duty_progress (system_id, obligation_key) values (%s, 'ai-literacy')",
        "insert into interview_answers (system_id, template, question_key, answer)"
        " values (%s, 'annex_iv', 'intended_purpose', 'x')",
    ),
    "not matching": (
        "insert into duty_progress (system_id, obligation_key) values (%s, 'risk-management')",
        "insert into interview_answers (system_id, template, question_key, answer)"
        " values (%s, 'art_27', 'other', 'x')",
    ),
}
"""B's rows under A's system, each matching one of A's rows on the old unique keys, or not."""


@pytest.mark.parametrize("insert", [*UNDER_A_SYSTEM["matching"], *UNDER_A_SYSTEM["not matching"]])
def test_a_row_under_another_users_system_always_fails_its_foreign_key(
    db: psycopg.Connection, insert: LiteralString
) -> None:
    """Whether A has a matching row or not, B gets 23503: the error never tells B what A stored."""
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        system = _add_system(db)["systems"]  # run 1, an annex_iv answer, the ai-literacy tick
    with as_user(db, user_b), pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
        db.execute(insert, (system,))


def test_run_no_increases_per_system(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        first, second = _add_system(db)["systems"], _add_system(db, "Chatbot")["systems"]
        assert [_add_run(db, first), _add_run(db, first), _add_run(db, second)] == [2, 3, 2]
        # The server numbers the run, whatever the client sends.
        forged = _one(
            db,
            "insert into classifications"
            " (system_id, risk_class, status, law_version, result, run_no)"
            " values (%s, 'high_risk', 'decided', 'amended', '{}', 99) returning run_no",
            (first,),
        )
        assert forged == 4
        # The next number follows the highest one kept: an undone last run's number comes back.
        db.execute("delete from classifications where system_id = %s and run_no = 4", (first,))
        assert _add_run(db, first) == 4
        db.execute("delete from classifications where system_id = %s and run_no = 2", (first,))
        assert _add_run(db, first) == 5
        runs = db.execute(
            "select system_id = %s, array_agg(run_no order by run_no) from classifications"
            " group by 1 order by 1",
            (first,),
        ).fetchall()
    assert runs == [(False, [1, 2]), (True, [1, 3, 4, 5])]


def test_concurrent_runs_of_one_system_get_distinct_numbers(
    db_connection: psycopg.Connection,
) -> None:
    """Two sessions of one user add a run of the same system at once: the second waits for the
    first's storage lock, then reads its committed run_no and takes the next one."""
    admin = db_connection
    with (
        _committed_user(admin) as (user, rows),
        psycopg.connect(_database_url()) as first,
        psycopg.connect(_database_url()) as second,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        system = rows["systems"]
        second_pid = _pid(second)

        def run_second() -> int:
            with as_user(second, user), second.transaction():
                return _add_run(second, system)

        with as_user(first, user):
            first_run = _add_run(first, system)
            pending = pool.submit(run_second)
            _wait_until_blocked(admin, second_pid)
        first.commit()
        assert (first_run, pending.result(timeout=LOCK_WAIT_SECONDS)) == (2, 3)


@pytest.mark.parametrize(
    "inputs",
    [
        [],
        {"answers": {}},
        {"description": 5},
        {"description": "x" * 140_000},
    ],
)
def test_inputs_must_hold_a_description(db: psycopg.Connection, inputs: object) -> None:
    user = _create_user(db)
    with as_user(db, user):
        system = _add_system(db)["systems"]
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(ADD_RUN, (system, Jsonb(inputs)))
        assert _add_run(db, system, INPUTS) == 2


def test_a_duty_is_ticked_once_with_a_valid_key(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        system = _add_system(db)["systems"]  # ticks ai-literacy
        tick = (
            "insert into duty_progress (system_id, obligation_key, created_at) values (%s, %s, %s)"
        )
        with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
            db.execute(tick, (system, "ai-literacy", None))
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(tick, (system, "Risk management", None))
        with pytest.raises(psycopg.errors.DatetimeFieldOverflow), db.transaction():
            db.execute(tick, (system, "risk-management", "-infinity"))
        assert db.execute("delete from duty_progress").rowcount == 1  # unticking
        assert _counts(db, user)["duty_progress"] == 0


def test_my_data_counts_returns_the_your_data_counts(db: psycopg.Connection) -> None:
    user, other = _create_user(db), _create_user(db)
    with as_user(db, other):
        _add_system(db)
    empty = {
        **dict.fromkeys(USER_TABLES, 0),
        "company_profiles": 0,
        "storage_bytes": 0,
        "storage_budget_bytes": STORAGE_BUDGET,
    }
    with as_user(db, user):
        assert _one(db, "select my_data_counts()") == empty
        rows = _add_system(db)
        _add_system(db, "Chatbot")
        _set_profile(db, rows["inventories"], PROFILE)
        _add_classification(db, rows["systems"], 0)
        counts = _one(db, "select my_data_counts()")
    assert counts == {
        "inventories": 2,
        "company_profiles": 1,
        "systems": 2,
        "classifications": 3,
        "interview_answers": 2,
        "duty_progress": 2,
        "storage_bytes": _usage(db, user),
        "storage_budget_bytes": STORAGE_BUDGET,
    }
    assert counts["storage_bytes"] > 0


def test_my_data_counts_needs_a_session(db: psycopg.Connection) -> None:
    with as_user(db, None), pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("select my_data_counts()")


def test_the_round_trip_keeps_the_profile_runs_inputs_and_ticks(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        rows = _add_system(db)
        _set_profile(db, rows["inventories"], PROFILE)
        _add_run(db, rows["systems"], INPUTS)
        exported = _one(db, "select export_my_data()")
    inventory = exported["inventories"][0]
    assert {key: inventory[key] for key in PROFILE} == PROFILE
    system = inventory["systems"][0]
    assert [(run["run_no"], run["inputs"]) for run in system["classifications"]] == [
        (1, None),
        (2, INPUTS),
    ]
    assert [tick["obligation_key"] for tick in system["duty_progress"]] == ["ai-literacy"]

    with as_user(db, user_b):
        added = _one(db, "select import_my_data(%s)", (Jsonb(exported),))
        reexported = _one(db, "select export_my_data()")
        size_class = _one(db, "select size_class from inventories")
    assert added == {**dict.fromkeys(USER_TABLES, 1), "classifications": 2}
    assert reexported["inventories"] == exported["inventories"]
    assert size_class == "sme"
    assert _usage(db, user_b) == _usage(db, user_a)


def _age_rows(db: psycopg.Connection, user: UUID, tables: tuple[str, ...]) -> None:
    """Move the user's rows' activity 60 days back, past the timestamp trigger (as postgres; the
    replica role skips triggers for this transaction only)."""
    db.execute("set local session_replication_role = replica")
    for table in tables:
        db.execute(
            _on("update {} set updated_at = now() - interval '60 days' where user_id = %s", table),
            (user,),
        )
    db.execute("set local session_replication_role = origin")


def test_a_recent_tick_keeps_its_user_from_the_cleanup(db: psycopg.Connection) -> None:
    user = _create_user(db, age="60 days")
    with as_user(db, user):
        rows = _add_system(db)
        _set_profile(db, rows["inventories"], PROFILE)
    _age_rows(db, user, tuple(table for table in USER_TABLES if table != "duty_progress"))
    _purge(db, later="29 days")
    assert _user_exists(db, user)

    _age_rows(db, user, ("duty_progress",))
    _purge(db, later="29 days")
    assert not _user_exists(db, user)
    assert _counts(db, user) == dict.fromkeys(USER_TABLES, 0)
