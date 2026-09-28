"""The user-data migration (supabase/migrations/*_user_data.sql) against the local Supabase
Postgres: RLS between two anonymous users, delete my data, export/import and the
inactivity cleanup.

Each test runs as postgres inside the rolled-back `db` transaction; `as_user` switches to the
`authenticated` role with a JWT `sub`, the way PostgREST runs a request from an anonymous session.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
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


def _add_old_system(db: psycopg.Connection, user_id: UUID, age: str) -> None:
    """As postgres: one row per table for this user, created and last updated `age` ago (an
    update would reset updated_at, so the times are set on insert)."""
    params = {"user": user_id, "age": age}
    db.execute(
        """
        with inventory as (
          insert into inventories (user_id, name, created_at, updated_at)
          values (%(user)s, 'Old', now() - %(age)s::interval, now() - %(age)s::interval)
          returning id
        ), system as (
          insert into systems (user_id, inventory_id, name, description, created_at, updated_at)
          select %(user)s, id, 'Old', 'Old.', now() - %(age)s::interval, now() - %(age)s::interval
          from inventory
          returning id
        ), classification as (
          insert into classifications
            (user_id, system_id, risk_class, status, law_version, result, created_at)
          select %(user)s, id, 'minimal_risk', 'decided', 'amended', '{}', now() - %(age)s::interval
          from system
        )
        insert into interview_answers
          (user_id, system_id, template, question_key, answer, created_at, updated_at)
        select %(user)s, id, 'art_27', 'q', 'a',
               now() - %(age)s::interval, now() - %(age)s::interval
        from system
        """,
        params,
    )


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
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("select delete_my_data()")
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


def test_updates_bump_updated_at(db: psycopg.Connection) -> None:
    user = _create_user(db)
    _add_old_system(db, user, age="1 day")
    with as_user(db, user):
        db.execute("update inventories set name = 'Renamed'")
        db.execute("update systems set name = 'Renamed'")
        db.execute("update interview_answers set answer = 'Changed'")
        for table in ("inventories", "systems", "interview_answers"):
            assert _one(db, _on("select bool_and(updated_at = now()) from {}", table))


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


def test_export_then_import_copies_the_data_into_another_session(
    db: psycopg.Connection, two_users: tuple[UUID, UUID, dict[str, UUID]]
) -> None:
    user_a, user_b, rows = two_users
    with as_user(db, user_a):
        exported = _one(db, "select export_my_data()")
    assert exported["format"] == "aiact-user-data"
    assert exported["version"] == 1
    [inventory] = exported["inventories"]
    [system] = inventory["systems"]
    assert "id" not in inventory and "user_id" not in system
    assert system["classifications"][0]["result"] == RESULT
    assert system["interview_answers"] == [
        {"template": "annex_iv", "question_key": "intended_purpose", "answer": "Shortlisting."}
    ]

    with as_user(db, user_b):
        added = _one(db, "select import_my_data(%s)", (Jsonb(exported),))
        assert added == dict.fromkeys(USER_TABLES, 1)
        reexported = _one(db, "select export_my_data()")
        assert (
            db.execute(
                "select id from inventories where id = %s", (rows["inventories"],)
            ).fetchall()
            == []
        )

    def content(document: dict[str, Any]) -> list[Any]:
        return document["inventories"]

    assert content(reexported) == content(exported)
    assert _counts(db, user_a) == dict.fromkeys(USER_TABLES, 1)


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


def _purge(db: psycopg.Connection, retention: str = RETENTION) -> int:
    return _one(db, "select private.purge_inactive_anonymous_users(%s::interval)", (retention,))


def _user_exists(db: psycopg.Connection, user_id: UUID) -> bool:
    return _one(db, "select exists (select 1 from auth.users where id = %s)", (user_id,))


def test_cleanup_deletes_inactive_anonymous_users_and_their_data(db: psycopg.Connection) -> None:
    stale = _create_user(db, age="31 days")
    _add_old_system(db, stale, age="31 days")
    fresh = _create_user(db, age="29 days")
    registered = _create_user(db, is_anonymous=False, age="400 days")

    assert _purge(db) >= 1  # the shared database may hold other stale anonymous users
    assert not _user_exists(db, stale)
    assert _counts(db, stale) == dict.fromkeys(USER_TABLES, 0)
    assert _user_exists(db, fresh)
    assert _user_exists(db, registered)


def test_cleanup_counts_recent_data_and_session_refreshes_as_activity(
    db: psycopg.Connection,
) -> None:
    edited = _create_user(db, age="60 days")
    with as_user(db, edited):
        _add_system(db)  # written now
    visited = _create_user(db, age="60 days")
    db.execute(
        "insert into auth.sessions (id, user_id, created_at, updated_at, refreshed_at)"
        " values (%s, %s, now() - interval '60 days', now() - interval '2 days', now())",
        (uuid4(), visited),
    )

    _purge(db)
    assert _user_exists(db, edited)
    assert _user_exists(db, visited)


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
