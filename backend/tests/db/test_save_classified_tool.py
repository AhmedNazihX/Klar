"""Saving a classified tool (supabase/migrations/*_save_classified_tool.sql and
*_save_run_on_existing_tool.sql, story P6): the inventory if needed, the system and its first run
in one transaction, as the caller, or the next run on a tool the caller already has; and the
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
SAVE_ON = "select save_classified_tool(null, 'AI inventory', %s, %s, %s, %s)"
RERUN_DESCRIPTION = "Ranks job applicants for our recruiters and drafts their rejection letters."
RERUN_RESULT = {
    "risk_class": "limited_risk",
    "status": "needs_more_information",
    "law_version": "original",
    "disclaimer": "Guidance only.",
}
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
        ("public.save_classified_tool(uuid, text, text, text, jsonb, uuid)",),
    )
    assert options is False
    # The five-argument version was replaced, not overloaded: one function, so one set of grants.
    signatures = db.execute(
        "select p.oid::regprocedure::text from pg_proc p"
        " where p.pronamespace = 'public'::regnamespace and p.proname = 'save_classified_tool'"
    ).fetchall()
    assert signatures == [("save_classified_tool(uuid,text,text,text,jsonb,uuid)",)]


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


def _save_on(
    db: psycopg.Connection,
    tool: UUID,
    name: str | None = "CV ranker",
    result: dict[str, Any] | None = None,
) -> UUID:
    return _one(db, SAVE_ON, (name, RERUN_DESCRIPTION, Jsonb(result or RERUN_RESULT), tool))


def _tool_and_runs(db: psycopg.Connection, tool: UUID) -> tuple[Any, ...]:
    """A tool's name and description, and each run's number, class and inputs (as postgres)."""
    row = db.execute(
        "select s.name, s.description,"
        " (select coalesce(jsonb_agg(jsonb_build_array(c.run_no, c.risk_class, c.inputs)"
        "  order by c.run_no), '[]') from classifications c where c.system_id = s.id)"
        " from systems s where s.id = %s",
        (tool,),
    ).fetchone()
    assert row is not None
    return tuple(row)


def test_a_run_on_an_existing_tool_is_its_next_run(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        tool = _save(db, None)
        assert _save_on(db, tool) == tool
        latest = db.execute("select name, description, run_no, result from inventory_tools")
        assert latest.fetchall() == [("CV ranker", RERUN_DESCRIPTION, 2, RERUN_RESULT)]
    assert _tool_and_runs(db, tool) == (
        "CV ranker",
        RERUN_DESCRIPTION,
        [
            [1, "high_risk", {"description": DESCRIPTION, "answers": {}}],
            [2, "limited_risk", {"description": RERUN_DESCRIPTION, "answers": {}}],
        ],
    )
    assert _owned(db, user) == (1, 1, 2)


def test_a_tool_restored_without_runs_gets_its_first(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        inventory = _one(db, "insert into inventories (name) values ('Acme') returning id")
        tool = _one(
            db,
            "insert into systems (inventory_id, name, description) values (%s, %s, %s)"
            " returning id",
            (inventory, "CV screener", DESCRIPTION),
        )
        assert _save_on(db, tool, name="CV screener") == tool
    assert _tool_and_runs(db, tool) == (
        "CV screener",
        RERUN_DESCRIPTION,
        [[1, "limited_risk", {"description": RERUN_DESCRIPTION, "answers": {}}]],
    )
    assert _owned(db, user) == (1, 1, 1)


def test_nobody_adds_a_run_to_another_users_tool(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        tool = _save(db, None)
    before = _tool_and_runs(db, tool)
    with as_user(db, user_b), _raises_sqlstate(db, FOREIGN_KEY):
        _save_on(db, tool)
    # Neither a run nor the new name and description reached user A's tool.
    assert _tool_and_runs(db, tool) == before
    assert _owned(db, user_a) == (1, 1, 1)
    assert _owned(db, user_b) == (0, 0, 0)


def test_a_failed_run_on_an_existing_tool_changes_nothing(db: psycopg.Connection) -> None:
    user = _create_user(db)
    without_class = {key: value for key, value in RERUN_RESULT.items() if key != "risk_class"}
    with as_user(db, user):
        tool = _save(db, None)
    before = _tool_and_runs(db, tool)
    with as_user(db, user), _raises_sqlstate(db, NOT_NULL):
        _save_on(db, tool, result=without_class)
    # The new name and description are written before the run: its failure takes them back too.
    assert _tool_and_runs(db, tool) == before
    assert _owned(db, user) == (1, 1, 1)
