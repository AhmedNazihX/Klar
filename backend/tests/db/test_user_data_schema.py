"""The user-data migration (supabase/migrations/*_user_data.sql) against the local Supabase
Postgres: RLS between two anonymous users, delete my data, export/import and the
inactivity cleanup.

Each test runs as postgres inside the rolled-back `db` transaction; `as_user` switches to the
`authenticated` role with a JWT `sub`, the way PostgREST runs a request from an anonymous session.
"""

import json
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, LiteralString
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.abc import Params, QueryNoTemplate
from psycopg.types.json import Jsonb

from tests.db.conftest import _database_url

pytestmark = pytest.mark.db

USER_TABLES = ("inventories", "systems", "classifications", "interview_answers")
CRON_JOB = "purge-inactive-anonymous-users"
RETENTION = "30 days"
RESULT = {"risk_class": "high_risk", "law_version": "amended", "disclaimer": "Guidance only."}
RESULT_MAX_BYTES = 262144
FUTURE = "2999-01-01T00:00:00+00:00"
EMPTY_EXPORT = {"format": "aiact-user-data", "version": 1, "inventories": []}
RPC_CALLS = ("select delete_my_data()", "select export_my_data()", "select import_my_data(%s)")


def _create_user(db: psycopg.Connection, *, is_anonymous: bool = True, age: str = "0 days") -> UUID:
    """An auth user whose sign-in, creation and update times all lie `age` in the past."""
    user_id = uuid4()
    db.execute(
        """
        insert into auth.users
          (id, aud, role, is_anonymous, created_at, updated_at, last_sign_in_at)
        values (%(id)s, 'authenticated', 'authenticated', %(anon)s,
                now() - %(age)s::interval, now() - %(age)s::interval, now() - %(age)s::interval)
        """,
        {"id": user_id, "anon": is_anonymous, "age": age},
    )
    return user_id


@contextmanager
def as_user(db: psycopg.Connection, user_id: UUID | None) -> Iterator[psycopg.Connection]:
    """Run as `authenticated` with this user's JWT (no `sub` when None), then back to postgres."""
    claims = {"role": "authenticated"} if user_id is None else {"sub": str(user_id)}
    db.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
    db.execute("set local role authenticated")
    try:
        yield db
    finally:
        db.execute("reset role")
        db.execute("select set_config('request.jwt.claims', '', true)")


def _one(db: psycopg.Connection, query: QueryNoTemplate, params: Params | None = None) -> Any:
    row = db.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def _add_system(db: psycopg.Connection, name: str = "CV screener") -> dict[str, UUID]:
    """As the current user: an inventory with one system, a classification and an answer."""
    inventory = _one(db, "insert into inventories (name) values ('Acme') returning id")
    system = _one(
        db,
        "insert into systems (inventory_id, name, description) values (%s, %s, %s) returning id",
        (inventory, name, "Ranks job applicants."),
    )
    classification = _one(
        db,
        """
        insert into classifications (system_id, risk_class, status, law_version, result)
        values (%s, 'high_risk', 'decided', 'amended', %s) returning id
        """,
        (system, Jsonb(RESULT)),
    )
    answer = _one(
        db,
        """
        insert into interview_answers (system_id, template, question_key, answer)
        values (%s, 'annex_iv', 'intended_purpose', 'Shortlisting.') returning id
        """,
        (system,),
    )
    return {
        "inventories": inventory,
        "systems": system,
        "classifications": classification,
        "interview_answers": answer,
    }


def _on(template: LiteralString, table: str) -> sql.Composed:
    """`template` with its `{}` filled by the quoted table name."""
    return sql.SQL(template).format(sql.Identifier(table))


def _counts(db: psycopg.Connection, user_id: UUID) -> dict[str, int]:
    return {
        table: _one(db, _on("select count(*) from {} where user_id = %s", table), (user_id,))
        for table in USER_TABLES
    }


@pytest.fixture
def two_users(db: psycopg.Connection) -> tuple[UUID, UUID, dict[str, UUID]]:
    """Users A and B; A owns one row in every table."""
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        rows = _add_system(db)
    return user_a, user_b, rows


def test_every_user_table_has_rls_and_owner_policies(db: psycopg.Connection) -> None:
    for table in USER_TABLES:
        assert _one(db, "select relrowsecurity from pg_class where oid = %s::regclass", (table,))
        policies = db.execute(
            "select cmd, roles::text[], qual, with_check from pg_policies"
            " where schemaname = 'public' and tablename = %s",
            (table,),
        ).fetchall()
        assert policies
        for _cmd, roles, qual, with_check in policies:
            assert roles == ["authenticated"]
            assert all(clause is None or "auth.uid()" in clause for clause in (qual, with_check))


def test_user_a_sees_their_rows_and_user_b_sees_none(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, user_b, rows = two_users
    with as_user(db, user_a):
        for table in USER_TABLES:
            assert db.execute(_on("select id from {}", table)).fetchall() == [(rows[table],)]
    with as_user(db, user_b):
        for table in USER_TABLES:
            assert db.execute(_on("select id from {}", table)).fetchall() == []


def test_user_b_cannot_change_or_delete_user_a_rows(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, user_b, rows = two_users
    with as_user(db, user_b):
        renamed = db.execute(
            "update inventories set name = 'Mine' where id = %s", (rows["inventories"],)
        )
        assert renamed.rowcount == 0
        for table in USER_TABLES:
            deleted = db.execute(_on("delete from {} where id = %s", table), (rows[table],))
            assert deleted.rowcount == 0
    assert _counts(db, user_a) == dict.fromkeys(USER_TABLES, 1)


def test_user_b_cannot_write_rows_owned_by_or_under_user_a(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, user_b, rows = two_users
    with as_user(db, user_b):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("insert into inventories (user_id, name) values (%s, 'Theirs')", (user_a,))
        # B's own row under A's inventory: the (inventory_id, user_id) foreign key has no match.
        with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
            db.execute(
                "insert into systems (inventory_id, name, description) values (%s, 'X', 'Y')",
                (rows["inventories"],),
            )
        own = _one(db, "insert into inventories (name) values ('Mine') returning id")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("update inventories set user_id = %s where id = %s", (user_a, own))


def test_anon_role_without_a_session_gets_no_access(db: psycopg.Connection) -> None:
    db.execute("set local role anon")
    try:
        for table in USER_TABLES:
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(_on("select 1 from {}", table))
        for call in RPC_CALLS:
            with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
                db.execute(call, (Jsonb(EMPTY_EXPORT),) if "%s" in call else None)
    finally:
        db.execute("reset role")


def test_classifications_cannot_be_rewritten(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, _, rows = two_users
    with as_user(db, user_a), pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(
            "update classifications set risk_class = 'minimal_risk' where id = %s",
            (rows["classifications"],),
        )


UPDATABLE_TABLES = ("inventories", "systems", "interview_answers")
"""Classifications are insert-and-delete only (see test_classifications_cannot_be_rewritten)."""

FORGED_INSERT = """
    with inventory as (
      insert into inventories (name, created_at, updated_at)
      values ('X', %(future)s, 'infinity') returning id
    ), system as (
      insert into systems (inventory_id, name, description, created_at, updated_at)
      select id, 'X', 'Y', %(future)s, 'infinity' from inventory returning id
    ), classification as (
      insert into classifications
        (system_id, risk_class, status, law_version, result, created_at, updated_at)
      select id, 'minimal_risk', 'decided', 'amended', '{}', %(future)s, 'infinity' from system
    )
    insert into interview_answers
      (system_id, template, question_key, answer, created_at, updated_at)
    select id, 'art_27', 'q', 'a', %(future)s, 'infinity' from system
"""


def _all_stamped_now(db: psycopg.Connection, table: str) -> bool:
    return _one(
        db, _on("select bool_and(created_at <= now() and updated_at = now()) from {}", table)
    )


def test_timestamps_are_set_by_the_server_on_insert(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        db.execute(FORGED_INSERT, {"future": FUTURE})
        for table in USER_TABLES:
            assert _one(db, _on("select count(*) from {}", table)) == 1
            assert _all_stamped_now(db, table)
        past = _one(
            db,
            "insert into inventories (name, created_at) values ('Y', now() - interval '3 days')"
            " returning now() - created_at",
        )
        assert past == timedelta(days=3)


def test_timestamps_are_set_by_the_server_on_update(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        _add_system(db)
        for table in UPDATABLE_TABLES:
            db.execute(
                _on("update {} set created_at = %s, updated_at = %s", table),
                (FUTURE, "infinity"),
            )
            assert _all_stamped_now(db, table)


CREATED_AT_FLOOR = datetime(2026, 9, 28, tzinfo=UTC)
"""The earliest created_at a row may have: the day the user-data schema went in."""


@pytest.mark.parametrize(
    "created_at", ["-infinity", "0001-01-01T00:00:00+00:00", "2026-09-27T23:59:59.999999+00:00"]
)
def test_a_created_at_before_the_floor_is_rejected(db: psycopg.Connection, created_at: str) -> None:
    user = _create_user(db)
    with as_user(db, user):
        with pytest.raises(psycopg.errors.DatetimeFieldOverflow), db.transaction():
            db.execute("insert into inventories (name, created_at) values ('X', %s)", (created_at,))
        system = {"name": "X", "description": "Y", "created_at": created_at}
        document = {**EMPTY_EXPORT, "inventories": [{"name": "Z", "systems": [system]}]}
        with pytest.raises(psycopg.errors.DatetimeFieldOverflow), db.transaction():
            db.execute("select import_my_data(%s)", (Jsonb(document),))
        floor = _one(
            db,
            "insert into inventories (name, created_at) values ('X', %s) returning created_at",
            (CREATED_AT_FLOOR,),
        )
    assert floor == CREATED_AT_FLOOR
    assert _counts(db, user) == {**dict.fromkeys(USER_TABLES, 0), "inventories": 1}


def test_an_import_older_than_its_new_owner_keeps_its_dates_and_order(
    db: psycopg.Connection,
) -> None:
    user = _create_user(db)  # signed up now, after every date in the file
    earlier, later = CREATED_AT_FLOOR + timedelta(hours=1), CREATED_AT_FLOOR + timedelta(hours=2)
    document = {
        **EMPTY_EXPORT,
        "inventories": [
            {"name": "Later", "created_at": later.isoformat()},
            {"name": "Earlier", "created_at": earlier.isoformat()},
        ],
    }
    with as_user(db, user):
        db.execute("select import_my_data(%s)", (Jsonb(document),))
        rows = db.execute("select name, created_at from inventories order by created_at").fetchall()
        exported = _one(db, "select export_my_data()")
    assert rows == [("Earlier", earlier), ("Later", later)]
    assert [inventory["name"] for inventory in exported["inventories"]] == ["Earlier", "Later"]


def test_a_classification_result_has_a_size_limit(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, _, rows = two_users
    oversized = {"text": "x" * RESULT_MAX_BYTES}
    with as_user(db, user_a), pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            """
            insert into classifications (system_id, risk_class, status, law_version, result)
            values (%s, 'high_risk', 'decided', 'amended', %s)
            """,
            (rows["systems"], Jsonb(oversized)),
        )


def test_delete_my_data_removes_only_the_callers_rows(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, user_b, _ = two_users
    with as_user(db, user_b):
        _add_system(db)
        _add_system(db, "Chatbot")
        assert _one(db, "select delete_my_data()") == {
            "inventories": 2,
            "systems": 2,
            "classifications": 2,
            "interview_answers": 2,
        }
    assert _counts(db, user_b) == dict.fromkeys(USER_TABLES, 0)
    assert _counts(db, user_a) == dict.fromkeys(USER_TABLES, 1)


def test_delete_my_data_needs_a_session(db: psycopg.Connection) -> None:
    with as_user(db, None), pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("select delete_my_data()")


def _add_dated_inventory(db: psycopg.Connection, name: str, days_ago: int) -> None:
    """As the current user: an inventory and one system, both created `days_ago` days ago."""
    db.execute(
        """
        with inventory as (
          insert into inventories (name, created_at)
          values (%(name)s, now() - make_interval(days => %(days)s))
          returning id, created_at
        ), system as (
          insert into systems (inventory_id, name, description, created_at)
          select id, %(name)s || ' system', 'Ranks job applicants.', created_at from inventory
          returning id, created_at
        )
        insert into classifications (system_id, risk_class, status, law_version, result, created_at)
        select id, 'high_risk', 'decided', 'amended', %(result)s, created_at from system
        """,
        {"name": name, "days": days_ago, "result": Jsonb(RESULT)},
    )


def test_export_then_import_keeps_content_dates_and_order(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        _add_dated_inventory(db, "Second", days_ago=1)  # inserted first, created later
        _add_dated_inventory(db, "First", days_ago=3)
        exported = _one(db, "select export_my_data()")
    assert exported["format"] == "aiact-user-data"
    assert exported["version"] == 1
    inventories = exported["inventories"]
    assert [inventory["name"] for inventory in inventories] == ["First", "Second"]
    system = inventories[0]["systems"][0]
    assert "id" not in inventories[0] and "user_id" not in system
    assert system["classifications"][0]["result"] == RESULT

    with as_user(db, user_b):
        added = _one(db, "select import_my_data(%s)", (Jsonb(exported),))
        assert added == {
            "inventories": 2,
            "systems": 2,
            "classifications": 2,
            "interview_answers": 0,
        }
        reexported = _one(db, "select export_my_data()")
    assert reexported["inventories"] == inventories

    # The dates are the file's, not the import's now().
    dates = db.execute(
        "select user_id = %s, name, now() - created_at from inventories"
        " where user_id in (%s, %s) order by user_id = %s, created_at",
        (user_b, user_a, user_b, user_b),
    ).fetchall()
    ages = [timedelta(days=3), timedelta(days=1)]
    assert dates == [
        *((False, name, age) for name, age in zip(("First", "Second"), ages, strict=True)),
        *((True, name, age) for name, age in zip(("First", "Second"), ages, strict=True)),
    ]
    assert _counts(db, user_a) == {**dict.fromkeys(USER_TABLES, 2), "interview_answers": 0}


IMPORT_MAX_BYTES = 4 * 1024 * 1024
"""import_my_data's cap: one import needs about 20 times this in memory (decision 027)."""

STORAGE_BUDGET = IMPORT_MAX_BYTES - 1024
"""Bytes a user's rows may add to their export; 1 kB is left for the export's envelope."""

MAX_RESULT_TEXT = RESULT_MAX_BYTES - len('{"text": ""}')
"""The longest `text` a {"text": ...} result can hold under the 256 kB result cap."""

STORAGE_FULL = "PT507"
IMPORT_TOO_LARGE = "PT413"
LOCK_WAIT_SECONDS = 10

ADD_CLASSIFICATION = """
    insert into classifications (system_id, risk_class, status, law_version, result, created_at)
    values (%(system)s, 'high_risk', 'decided', 'amended',
            jsonb_build_object('text', repeat('x', %(length)s::integer)),
            now() - make_interval(secs => %(age)s::integer))
"""


def _add_classification(db: psycopg.Connection, system: UUID, length: int, age: int = 0) -> None:
    """As the current user: a classification whose result text is `length` long, `age` s old."""
    db.execute(ADD_CLASSIFICATION, {"system": system, "length": length, "age": age})


@contextmanager
def _raises_sqlstate(db: psycopg.Connection, sqlstate: str) -> Iterator[None]:
    """The block fails with this SQLSTATE (inside a savepoint, so the test can go on)."""
    with pytest.raises(psycopg.Error) as caught, db.transaction():
        yield
    assert caught.value.sqlstate == sqlstate


def _usage(db: psycopg.Connection, user_id: UUID) -> int:
    """The user's running storage total (as postgres)."""
    row = db.execute(
        "select bytes from private.storage_usage where user_id = %s", (user_id,)
    ).fetchone()
    return row[0] if row else 0


def _classification_bytes(db: psycopg.Connection, length: int) -> int:
    """The stored size of an ADD_CLASSIFICATION row whose text is `length` long (as postgres)."""
    row = {
        "risk_class": "high_risk",
        "status": "decided",
        "law_version": "amended",
        "result": {"text": "x" * length},
    }
    return _one(db, "select private.export_bytes('classifications', %s)", (Jsonb(row),))


def _filler_lengths(free: int, base: int, largest: int) -> list[int]:
    """Result text lengths whose rows take exactly `free` bytes (at least one row)."""
    count = (free - base) // largest
    rest = free - count * largest  # base <= rest < largest + base
    if rest - base <= MAX_RESULT_TEXT:
        return [MAX_RESULT_TEXT] * count + [rest - base]
    # Too much for one row: a row of `largest - base` bytes, and the rest (over `base`) in another.
    return [MAX_RESULT_TEXT] * count + [MAX_RESULT_TEXT - base, rest - largest]


def _fill(db: psycopg.Connection, user_id: UUID, system: UUID, leave: int) -> None:
    """Classifications of `system` until exactly `leave` bytes of the budget are free (as postgres,
    acting as `user_id`)."""
    largest, base = _classification_bytes(db, MAX_RESULT_TEXT), _classification_bytes(db, 0)
    free = STORAGE_BUDGET - _usage(db, user_id) - leave
    lengths = _filler_lengths(free, base, largest)
    # Fail fast if export_bytes stops growing with the text: the fill would never end.
    assert largest - base == MAX_RESULT_TEXT
    assert len(lengths) <= STORAGE_BUDGET // MAX_RESULT_TEXT + 2
    with as_user(db, user_id):
        for offset, length in enumerate(lengths):
            _add_classification(db, system, length, age=offset + 1)
    assert _usage(db, user_id) == STORAGE_BUDGET - leave


def _user_with_system(db: psycopg.Connection) -> tuple[UUID, dict[str, UUID]]:
    user = _create_user(db)
    with as_user(db, user):
        return user, _add_system(db)


def test_an_export_at_the_full_budget_imports_and_round_trips(db: psycopg.Connection) -> None:
    (user_a, rows), user_b = _user_with_system(db), _create_user(db)
    _fill(db, user_a, rows["systems"], leave=0)
    with as_user(db, user_a):
        exported = _one(db, "select export_my_data()")
    size = _one(db, "select octet_length(%s::jsonb::text)", (Jsonb(exported),))
    assert IMPORT_MAX_BYTES - 2048 < size <= IMPORT_MAX_BYTES

    with as_user(db, user_b):
        db.execute("select import_my_data(%s)", (Jsonb(exported),))
        reexported = _one(db, "select export_my_data()")
    assert reexported["inventories"] == exported["inventories"]
    assert _usage(db, user_b) == _usage(db, user_a) == STORAGE_BUDGET


def _padded_document(db: psycopg.Connection, size: int) -> dict[str, Any]:
    """An empty export whose text is exactly `size` bytes (import ignores the extra key)."""
    base = _one(db, "select octet_length(%s::jsonb::text)", (Jsonb({**EMPTY_EXPORT, "pad": ""}),))
    return {**EMPTY_EXPORT, "pad": "x" * (size - base)}


def test_an_import_is_capped_at_four_megabytes(db: psycopg.Connection) -> None:
    user = _create_user(db)
    at_cap, over_cap = (
        _padded_document(db, IMPORT_MAX_BYTES),
        _padded_document(db, IMPORT_MAX_BYTES + 1),
    )
    with as_user(db, user):
        added = _one(db, "select import_my_data(%s)", (Jsonb(at_cap),))
        assert added == dict.fromkeys(USER_TABLES, 0)
        with _raises_sqlstate(db, IMPORT_TOO_LARGE):
            db.execute("select import_my_data(%s)", (Jsonb(over_cap),))


def test_the_budget_rejects_a_write_that_would_exceed_it(db: psycopg.Connection) -> None:
    user, rows = _user_with_system(db)
    _fill(db, user, rows["systems"], leave=_classification_bytes(db, 10))
    with as_user(db, user):
        with _raises_sqlstate(db, STORAGE_FULL):
            _add_classification(db, rows["systems"], 11)
        with _raises_sqlstate(db, STORAGE_FULL):
            db.execute("update interview_answers set answer = answer || repeat('y', 1000)")
        _add_classification(db, rows["systems"], 10)
    assert _usage(db, user) == STORAGE_BUDGET


def test_deleting_frees_space(db: psycopg.Connection) -> None:
    user, rows = _user_with_system(db)
    _fill(db, user, rows["systems"], leave=0)
    with as_user(db, user):
        with _raises_sqlstate(db, STORAGE_FULL):
            _add_classification(db, rows["systems"], 0)
        db.execute("delete from classifications where id = %s", (rows["classifications"],))
        _add_classification(db, rows["systems"], 0)
        # Shrinking always passes, and deleting everything brings the total back to zero.
        db.execute("update interview_answers set answer = ''")
        db.execute("select delete_my_data()")
    assert _usage(db, user) == 0


SECOND_ROWS: dict[str, LiteralString] = {
    "inventories": "insert into inventories (name, created_at) values ('Zweite \"Liste\"', %(at)s)"
    " returning to_jsonb(inventories)",
    "systems": "insert into systems (inventory_id, name, description, created_at)"
    " values (%(inventory)s, 'Bewerber-Ranking', 'Sortiert Bewerbungen für Ärzte.', %(at)s)"
    " returning to_jsonb(systems)",
    "classifications": "insert into classifications"
    " (system_id, risk_class, status, law_version, result, created_at)"
    " values (%(system)s, 'minimal_risk', 'decided', 'original', '{\"a\": \"é\", \"b\": [1]}',"
    " %(at)s) returning to_jsonb(classifications)",
    "interview_answers": "insert into interview_answers (system_id, template, question_key, answer)"
    " values (%(system)s, 'art_27', 'q2', 'Line one\nline \"two\".')"
    " returning to_jsonb(interview_answers)",
}
"""A second row per table (so each export array already has a first child), with quotes, accents
and a newline that the export's text escapes."""

FULL_PRECISION_TIME = "2026-09-30T12:34:56.123456+00:00"
"""A created_at that renders at its widest (32 characters) in UTC."""


def _export_size(db: psycopg.Connection) -> int:
    return _one(db, "select octet_length(export_my_data()::text)")


@pytest.mark.parametrize("table", USER_TABLES)
def test_a_rows_stored_size_is_what_it_adds_to_the_export(
    db: psycopg.Connection, table: str
) -> None:
    user, rows = _user_with_system(db)
    db.execute("set local timezone = 'UTC'")
    params = {
        "at": FULL_PRECISION_TIME,
        "inventory": rows["inventories"],
        "system": rows["systems"],
    }
    with as_user(db, user):
        before = _export_size(db)
        row = _one(db, SECOND_ROWS[table], params)
        growth = _export_size(db) - before
    assert _one(db, "select private.export_bytes(%s, %s)", (table, Jsonb(row))) == growth


def test_a_write_that_does_not_grow_the_data_passes_over_the_budget(
    db: psycopg.Connection,
) -> None:
    user, rows = _user_with_system(db)
    db.execute(
        "update private.storage_usage set bytes = %s where user_id = %s",
        (STORAGE_BUDGET + 1000, user),
    )
    with as_user(db, user):
        db.execute("update interview_answers set answer = ''")
        db.execute("update inventories set name = name")
        with _raises_sqlstate(db, STORAGE_FULL):
            db.execute("update inventories set name = name || 'x'")
        with _raises_sqlstate(db, STORAGE_FULL):
            _add_classification(db, rows["systems"], 0)


def test_an_import_past_the_budget_adds_nothing(db: psycopg.Connection) -> None:
    (user_a, _), (user_b, rows_b) = _user_with_system(db), _user_with_system(db)
    with as_user(db, user_a):
        exported = _one(db, "select export_my_data()")
    _fill(db, user_b, rows_b["systems"], leave=100)
    before = _counts(db, user_b)
    with as_user(db, user_b), _raises_sqlstate(db, STORAGE_FULL):
        db.execute("select import_my_data(%s)", (Jsonb(exported),))
    assert _counts(db, user_b) == before
    assert _usage(db, user_b) == STORAGE_BUDGET - 100


def _wait_until_blocked(admin: psycopg.Connection, pid: int) -> None:
    """Return once backend `pid` waits for a lock; fail after LOCK_WAIT_SECONDS."""
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    query = "select wait_event_type = 'Lock' from pg_stat_activity where pid = %s"
    while _one(admin, query, (pid,)) is not True:
        assert time.monotonic() < deadline, f"backend {pid} never waited for a lock"
        admin.rollback()  # pg_stat_activity is a snapshot per transaction
    admin.rollback()


@contextmanager
def _committed_user(admin: psycopg.Connection) -> Iterator[tuple[UUID, dict[str, UUID]]]:
    """A user with one row per table, committed so that other sessions see it (the lock tests
    need two real sessions), and deleted with all their data afterwards."""
    admin.rollback()
    user, rows = _user_with_system(admin)
    admin.commit()
    try:
        yield user, rows
    finally:
        admin.rollback()
        admin.execute("delete from auth.users where id = %s", (user,))
        admin.commit()


def _pid(connection: psycopg.Connection) -> int:
    pid = _one(connection, "select pg_backend_pid()")
    connection.rollback()
    return pid


def test_concurrent_writes_cannot_both_pass_the_budget(db_connection: psycopg.Connection) -> None:
    """Two sessions of one user, room for one more row: the second waits for the first, then
    fails."""
    admin = db_connection
    with (
        _committed_user(admin) as (user, rows),
        psycopg.connect(_database_url()) as first,
        psycopg.connect(_database_url()) as second,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        system = rows["systems"]
        _fill(admin, user, system, leave=_classification_bytes(admin, 0))
        admin.commit()
        second_pid = _pid(second)

        def write_second() -> None:
            with as_user(second, user), second.transaction():
                _add_classification(second, system, 0)

        with as_user(first, user):
            _add_classification(first, system, 0)
            pending = pool.submit(write_second)
            _wait_until_blocked(admin, second_pid)
        first.commit()
        with pytest.raises(psycopg.Error) as caught:
            pending.result(timeout=LOCK_WAIT_SECONDS)
        assert caught.value.sqlstate == STORAGE_FULL
    assert _usage(admin, user) == 0


def test_a_delete_racing_an_insert_does_not_deadlock(db_connection: psycopg.Connection) -> None:
    """delete_my_data's order (answers, then systems) against an insert under one of the systems.
    Every writer locks the user's storage total before any row, so the insert waits without holding
    its system's KEY SHARE lock, and the delete of the systems never waits for it."""
    admin = db_connection
    with (
        _committed_user(admin) as (user, rows),
        psycopg.connect(_database_url()) as deleting,
        psycopg.connect(_database_url()) as inserting,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        inserting_pid = _pid(inserting)

        def insert() -> None:
            with as_user(inserting, user), inserting.transaction():
                _add_classification(inserting, rows["systems"], 0)

        with as_user(deleting, user):
            deleting.execute("delete from interview_answers")
            pending = pool.submit(insert)
            _wait_until_blocked(admin, inserting_pid)
            deleting.execute("set local lock_timeout = '3s'")
            deleting.execute("delete from systems")
        deleting.rollback()
        pending.result(timeout=LOCK_WAIT_SECONDS)  # the insert goes ahead, no 40P01
        inserting.rollback()


@pytest.mark.parametrize(
    "document",
    [
        {"format": "something-else", "version": 1, "inventories": []},
        {"format": "aiact-user-data", "version": 2, "inventories": []},
        {"format": "aiact-user-data", "version": 1},
    ],
)
def test_import_rejects_other_files(db: psycopg.Connection, document: dict[str, Any]) -> None:
    user = _create_user(db)
    with as_user(db, user), pytest.raises(psycopg.errors.InvalidParameterValue), db.transaction():
        db.execute("select import_my_data(%s)", (Jsonb(document),))


def test_import_with_an_invalid_row_adds_nothing(db: psycopg.Connection) -> None:
    user = _create_user(db)
    document = {
        "format": "aiact-user-data",
        "version": 1,
        "inventories": [
            {"name": "Good", "systems": []},
            {
                "name": "Bad",
                "systems": [
                    {
                        "name": "X",
                        "description": "Y",
                        "classifications": [
                            {
                                "risk_class": "very_risky",
                                "status": "decided",
                                "law_version": "amended",
                                "result": {},
                            }
                        ],
                    }
                ],
            },
        ],
    }
    with as_user(db, user), pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute("select import_my_data(%s)", (Jsonb(document),))
    assert _counts(db, user) == dict.fromkeys(USER_TABLES, 0)


def _purge(db: psycopg.Connection, retention: str = RETENTION, later: str = "0 days") -> int:
    """Run the cleanup as if it were `later` from now."""
    return _one(
        db,
        "select private.purge_inactive_anonymous_users(%s::interval, now() + %s::interval)",
        (retention, later),
    )


def _user_exists(db: psycopg.Connection, user_id: UUID) -> bool:
    return _one(db, "select exists (select 1 from auth.users where id = %s)", (user_id,))


def test_cleanup_deletes_inactive_anonymous_users_and_their_data(db: psycopg.Connection) -> None:
    stale = _create_user(db, age="1 day")
    with as_user(db, stale):
        _add_system(db)
    registered = _create_user(db, is_anonymous=False, age="400 days")

    assert _purge(db, later="31 days") >= 1  # the shared database may hold other stale users
    assert not _user_exists(db, stale)
    assert _counts(db, stale) == dict.fromkeys(USER_TABLES, 0)
    assert _user_exists(db, registered)


def test_cleanup_keeps_users_active_within_the_retention(db: psycopg.Connection) -> None:
    edited = _create_user(db, age="60 days")
    with as_user(db, edited):
        _add_system(db)  # written now
    visited = _create_user(db, age="60 days")
    db.execute(
        "insert into auth.sessions (id, user_id, created_at, updated_at, refreshed_at)"
        " values (%s, %s, now() - interval '60 days', now() - interval '60 days', now())",
        (uuid4(), visited),
    )
    idle = _create_user(db, age="60 days")

    _purge(db, later="29 days")
    assert _user_exists(db, edited)
    assert _user_exists(db, visited)
    assert not _user_exists(db, idle)


def test_a_future_timestamp_written_directly_does_not_block_the_cleanup(
    db: psycopg.Connection,
) -> None:
    user = _create_user(db, age="90 days")
    with as_user(db, user):
        db.execute(
            "insert into inventories (name, created_at, updated_at) values ('X', %s, 'infinity')",
            (FUTURE,),
        )
        db.execute("update inventories set updated_at = 'infinity', created_at = %s", (FUTURE,))

    _purge(db, later="31 days")
    assert not _user_exists(db, user)


def test_a_future_timestamp_in_an_import_does_not_block_the_cleanup(
    db: psycopg.Connection,
) -> None:
    user = _create_user(db, age="90 days")
    classification = {
        "risk_class": "minimal_risk",
        "status": "decided",
        "law_version": "amended",
        "result": {},
        "created_at": FUTURE,
    }
    system = {
        "name": "X",
        "description": "Y",
        "created_at": FUTURE,
        "classifications": [classification],
    }
    document = {
        **EMPTY_EXPORT,
        "inventories": [{"name": "Z", "created_at": FUTURE, "systems": [system]}],
    }
    with as_user(db, user):
        db.execute("select import_my_data(%s)", (Jsonb(document),))
        for table in ("inventories", "systems", "classifications"):
            assert _one(db, _on("select bool_and(created_at <= now()) from {}", table))

    _purge(db, later="31 days")
    assert not _user_exists(db, user)


def test_cleanup_refuses_a_retention_under_one_day(db: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.InvalidParameterValue), db.transaction():
        _purge(db, "1 hour")


def test_cleanup_is_not_callable_from_the_data_api_roles(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user), pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        _purge(db)


def test_cleanup_runs_daily_with_the_retention_period(db: psycopg.Connection) -> None:
    schedule, command = db.execute(
        "select schedule, command from cron.job where jobname = %s", (CRON_JOB,)
    ).fetchone() or (None, None)
    assert schedule == "17 3 * * *"
    assert command == f"select private.purge_inactive_anonymous_users(interval '{RETENTION}')"
