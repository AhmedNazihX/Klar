"""The user-data migration (supabase/migrations/*_user_data.sql) against the local Supabase
Postgres: RLS between two anonymous users, delete my data, export/import and the
inactivity cleanup.

Each test runs as postgres inside the rolled-back `db` transaction; `as_user` switches to the
`authenticated` role with a JWT `sub`, the way PostgREST runs a request from an anonymous session.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, LiteralString
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.abc import Params, QueryNoTemplate
from psycopg.types.json import Jsonb

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


def test_timestamps_are_set_by_the_server(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        _add_system(db)
        for table in USER_TABLES:
            db.execute(
                _on("update {} set created_at = %s, updated_at = %s", table),
                (FUTURE, "infinity"),
            )
            assert _one(
                db,
                _on("select bool_and(created_at <= now() and updated_at = now()) from {}", table),
            )
        forged = db.execute(
            "insert into inventories (name, created_at, updated_at) values ('X', %s, 'infinity')"
            " returning created_at = now() and updated_at = now()",
            (FUTURE,),
        ).fetchone()
        assert forged == (True,)
        past = _one(
            db,
            "insert into inventories (name, created_at) values ('Y', now() - interval '3 days')"
            " returning now() - created_at",
        )
        assert past == timedelta(days=3)


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
