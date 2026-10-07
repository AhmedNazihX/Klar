"""Saving a classified tool (supabase/migrations/*_save_classified_tool.sql, story P6): the
inventory if needed, the system and its first run in one transaction, as the caller; and the
optional tool name every reader of systems takes.
"""

from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.db.test_user_data_schema import (
    STORAGE_FULL,
    _create_user,
    _fill,
    _one,
    _raises_sqlstate,
    _user_with_system,
    as_user,
)

pytestmark = pytest.mark.db

DESCRIPTION = "Ranks job applicants for our recruiters."
RESULT = {
    "risk_class": "high_risk",
    "status": "decided",
    "law_version": "amended",
    "disclaimer": "Guidance only.",
}
SAVE = "select save_classified_tool(%s, 'AI inventory', %s, %s, %s)"
NO_SESSION = "42501"
NOT_NULL = "23502"
FOREIGN_KEY = "23503"
OLDEST_CREATED_AT = "2026-09-30T00:00:00+00:00"
"""After the user-data tables' created_at floor (2026-09-28) and before any test's now()."""


def _save(
    db: psycopg.Connection,
    inventory: UUID | None,
    name: str | None = "CV screener",
    result: dict[str, Any] | None = None,
) -> UUID:
    return _one(db, SAVE, (inventory, name, DESCRIPTION, Jsonb(result or RESULT)))


def _owned(db: psycopg.Connection, user: UUID) -> tuple[int, ...]:
    """The user's inventories, systems and classifications (as postgres)."""
    row = db.execute(
        "select (select count(*) from inventories where user_id = %(u)s),"
        " (select count(*) from systems where user_id = %(u)s),"
        " (select count(*) from classifications where user_id = %(u)s)",
        {"u": user},
    ).fetchone()
    assert row is not None
    return tuple(row)


def test_a_first_save_creates_the_inventory_the_tool_and_its_run(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        tool = _save(db, None)
        row = db.execute(
            "select t.name, t.description, t.run_no, t.result, i.name, c.inputs"
            " from inventory_tools t join inventories i on i.id = t.inventory_id"
            " join classifications c on c.system_id = t.id where t.id = %s",
            (tool,),
        ).fetchall()
    assert row == [
        (
            "CV screener",
            DESCRIPTION,
            1,
            RESULT,
            "AI inventory",
            {"description": DESCRIPTION, "answers": {}},
        )
    ]
    assert _owned(db, user) == (1, 1, 1)


def test_later_saves_go_into_the_given_or_the_oldest_inventory(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        # Inserted second but created first (an import keeps its dates): age decides, not order.
        newer = _one(db, "insert into inventories (name) values ('Newer') returning id")
        oldest = _one(
            db,
            "insert into inventories (name, created_at) values ('Oldest', %s) returning id",
            (OLDEST_CREATED_AT,),
        )
        into_newer = _save(db, newer)
        into_oldest = _save(db, None)
        placed = dict(
            db.execute(
                "select id, inventory_id from systems where id in (%s, %s)",
                (into_newer, into_oldest),
            ).fetchall()
        )
    assert placed == {into_newer: newer, into_oldest: oldest}


def test_an_unnamed_tool_is_stored_without_a_name(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        tool = _save(db, None, name=None)
        assert _one(db, "select name from inventory_tools where id = %s", (tool,)) is None


def test_a_failed_run_leaves_no_tool_and_no_inventory_behind(db: psycopg.Connection) -> None:
    user = _create_user(db)
    without_class = {key: value for key, value in RESULT.items() if key != "risk_class"}
    with as_user(db, user), _raises_sqlstate(db, NOT_NULL):
        _save(db, None, result=without_class)
    assert _owned(db, user) == (0, 0, 0)


def test_a_run_past_the_storage_budget_leaves_no_tool_behind(db: psycopg.Connection) -> None:
    user, rows = _user_with_system(db)
    system_bytes = _one(
        db,
        "select private.export_bytes('systems', %s)",
        (Jsonb({"name": "CV screener", "description": DESCRIPTION}),),
    )
    # Room for the system, but not for its run.
    _fill(db, user, rows["systems"], leave=system_bytes + 10)
    before = _owned(db, user)
    with as_user(db, user), _raises_sqlstate(db, STORAGE_FULL):
        _save(db, rows["inventories"])
    assert _owned(db, user) == before


def test_nobody_saves_into_another_users_inventory(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        tool = _save(db, None)
        inventory = _one(db, "select inventory_id from systems where id = %s", (tool,))
    with as_user(db, user_b):
        with _raises_sqlstate(db, FOREIGN_KEY):
            _save(db, inventory)
        assert db.execute("select id from inventory_tools").fetchall() == []
    assert _owned(db, user_b) == (0, 0, 0)
    assert _owned(db, user_a) == (1, 1, 1)


def test_a_save_needs_a_session(db: psycopg.Connection) -> None:
    with as_user(db, None), _raises_sqlstate(db, NO_SESSION):
        _save(db, None)

    db.execute("set local role anon")
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            _save(db, None)
    finally:
        db.execute("reset role")


def test_only_a_session_may_call_it(db: psycopg.Connection) -> None:
    grantees = db.execute(
        "select grantee from information_schema.routine_privileges"
        " where routine_schema = 'public' and routine_name = 'save_classified_tool'"
        " and grantee in ('anon', 'authenticated', 'PUBLIC') order by grantee"
    ).fetchall()
    assert grantees == [("authenticated",)]
    options = _one(
        db,
        "select prosecdef from pg_proc where oid = %s::regprocedure",
        ("public.save_classified_tool(uuid, text, text, text, jsonb)",),
    )
    assert options is False


def test_an_unnamed_tool_exports_and_a_file_without_names_imports(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        _save(db, None, name=None)
        exported = _one(db, "select export_my_data()")
    [system] = exported["inventories"][0]["systems"]
    assert system["name"] is None

    nameless = {
        "format": "aiact-user-data",
        "version": 1,
        "inventories": [{"name": "Acme", "systems": [{"description": DESCRIPTION}]}],
    }
    with as_user(db, user_b):
        db.execute("select import_my_data(%s)", (Jsonb(exported),))
        db.execute("select import_my_data(%s)", (Jsonb(nameless),))
        names = db.execute("select name, description from systems order by created_at").fetchall()
    assert names == [(None, DESCRIPTION), (None, DESCRIPTION)]
