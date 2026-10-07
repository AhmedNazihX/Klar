"""The inventory view (supabase/migrations/*_inventory_tools.sql, story P6): each of the caller's
tools with its latest run, through the owner-only RLS of the tables under it.

The Inventory screen and a tool's result page read it through the Data API as the anonymous
session; `as_user` runs these queries the same way.
"""

from typing import Any
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.db.test_user_data_schema import _create_user, _one, as_user

pytestmark = pytest.mark.db

VIEW = "inventory_tools"
SELECT_TOOLS = "select name, run_no, result from inventory_tools order by name"


def _add_tool(db: psycopg.Connection, inventory: UUID, name: str) -> UUID:
    """As the current user: a system in `inventory`, with no run yet."""
    return _one(
        db,
        "insert into systems (inventory_id, name, description) values (%s, %s, 'Ranks CVs.')"
        " returning id",
        (inventory, name),
    )


def _add_run(db: psycopg.Connection, system: UUID, result: dict[str, Any]) -> None:
    """As the current user: a run of `system` with this result."""
    db.execute(
        "insert into classifications (system_id, risk_class, status, law_version, result)"
        " values (%s, %s, 'decided', 'amended', %s)",
        (system, result["risk_class"], Jsonb(result)),
    )


def _inventory(db: psycopg.Connection) -> UUID:
    return _one(db, "insert into inventories (name) values ('AI inventory') returning id")


def test_each_tool_shows_its_latest_run_or_none(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        inventory = _inventory(db)
        rechecked = _add_tool(db, inventory, "Applicant screening")
        _add_run(db, rechecked, {"risk_class": "high_risk", "run": "first"})
        _add_run(db, rechecked, {"risk_class": "minimal_risk", "run": "second"})
        _add_tool(db, inventory, "Route planner")
        rows = db.execute(SELECT_TOOLS).fetchall()
    assert rows == [
        ("Applicant screening", 2, {"risk_class": "minimal_risk", "run": "second"}),
        ("Route planner", None, None),
    ]


def test_undoing_the_latest_run_shows_the_one_before(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        tool = _add_tool(db, _inventory(db), "Applicant screening")
        _add_run(db, tool, {"risk_class": "high_risk", "run": "first"})
        _add_run(db, tool, {"risk_class": "minimal_risk", "run": "second"})
        db.execute("delete from classifications where system_id = %s and run_no = 2", (tool,))
        rows = db.execute(SELECT_TOOLS).fetchall()
    assert rows == [("Applicant screening", 1, {"risk_class": "high_risk", "run": "first"})]


def test_a_tool_reads_by_its_id_with_its_description_and_inventory(db: psycopg.Connection) -> None:
    user = _create_user(db)
    with as_user(db, user):
        inventory = _inventory(db)
        tool = _add_tool(db, inventory, "Applicant screening")
        _add_tool(db, inventory, "Route planner")
        row = db.execute(
            "select id, inventory_id, name, description, checked_at from inventory_tools"
            " where id = %s",
            (tool,),
        ).fetchall()
    assert row == [(tool, inventory, "Applicant screening", "Ranks CVs.", None)]


def test_user_b_sees_none_of_user_a_tools(db: psycopg.Connection) -> None:
    user_a, user_b = _create_user(db), _create_user(db)
    with as_user(db, user_a):
        tool = _add_tool(db, _inventory(db), "Applicant screening")
        _add_run(db, tool, {"risk_class": "high_risk"})
        assert db.execute("select count(*) from inventory_tools").fetchone() == (1,)
    with as_user(db, user_b):
        assert db.execute("select count(*) from inventory_tools").fetchone() == (0,)
        assert db.execute("select id from inventory_tools where id = %s", (tool,)).fetchall() == []


def test_the_view_runs_as_the_caller(db: psycopg.Connection) -> None:
    options = _one(db, "select reloptions from pg_class where oid = %s::regclass", (VIEW,))
    assert options == ["security_invoker=true"]


def test_only_a_session_may_read_it_and_nobody_may_write_through_it(db: psycopg.Connection) -> None:
    grants = db.execute(
        "select grantee, privilege_type from information_schema.role_table_grants"
        " where table_schema = 'public' and table_name = %s and grantee in"
        " ('anon', 'authenticated', 'PUBLIC') order by grantee, privilege_type",
        (VIEW,),
    ).fetchall()
    assert grants == [("authenticated", "SELECT")]

    db.execute("set local role anon")
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute("select 1 from inventory_tools")
    finally:
        db.execute("reset role")
