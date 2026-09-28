"""The obligations migration (supabase/migrations/*_obligations.sql) and its seed, against the local
Supabase Postgres. Needs `supabase db reset` after the migration or the YAML changed."""

import psycopg
import pytest

from aiact.obligations.list import load_table

pytestmark = pytest.mark.db

INSERT = """
    insert into obligations
      (obligation_key, position, role, risk_class, high_risk_route, duty, article, applies_from,
       law_version)
    values ('test-duty', 0, %(role)s, %(risk_class)s, %(route)s, 'Do something.', %(article)s,
            '2026-08-02', 'amended')
"""
VALID = {"role": "provider", "risk_class": "high_risk", "route": None, "article": "art:16:a"}


def test_seeded_rows_match_the_yaml(db: psycopg.Connection) -> None:
    table = load_table()
    expected = [
        (
            row.key,
            row.role.value,
            row.risk_class.value,
            row.obligation.high_risk_route.value if row.obligation.high_risk_route else None,
            row.obligation.article,
            row.obligation.applies_from,
        )
        for row in table.rows()
    ]
    seeded = db.execute(
        "select obligation_key, role, risk_class, high_risk_route, article, applies_from"
        " from obligations where law_version = %s order by position",
        (table.law_version.value,),
    ).fetchall()
    assert seeded == expected


def test_a_valid_row_is_accepted(db: psycopg.Connection) -> None:
    db.execute(INSERT, VALID)


@pytest.mark.parametrize(
    "change",
    [
        {"route": "annex_iii", "risk_class": "limited_risk"},  # routes are for high-risk only
        {"article": "annex:III:4:a"},  # every row cites an article
        {"risk_class": "out_of_scope"},
        {"role": "authorised_representative"},
        {"route": "annex_ii"},
    ],
)
def test_invalid_rows_are_rejected(db: psycopg.Connection, change: dict[str, object]) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(INSERT, VALID | change)


def test_a_duty_is_listed_once_per_role_class_and_route(db: psycopg.Connection) -> None:
    db.execute(INSERT, VALID)
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(INSERT, VALID)


def test_data_api_roles_have_no_access(db: psycopg.Connection) -> None:
    row = db.execute(
        "select has_table_privilege('anon', 'public.obligations', 'select'),"
        " has_table_privilege('authenticated', 'public.obligations', 'select')"
    ).fetchone()
    assert row == (False, False)
