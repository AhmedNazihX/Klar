"""The obligations migrations (supabase/migrations/*_obligations.sql, *_obligation_texts.sql) and
the seed, against the local Supabase Postgres. After a new migration or a YAML change, apply it with
`supabase migration up --local` and reload supabase/seed/obligations.sql (never `supabase db
reset`: the database is shared)."""

import psycopg
import pytest

from aiact.obligations.list import load_table

pytestmark = pytest.mark.db

INSERT = """
    insert into obligations
      (obligation_key, position, role, risk_class, high_risk_route, duty, article, applies_from,
       law_version, label_en, label_de, duty_de, duty_group, document)
    values ('test-duty', 0, %(role)s, %(risk_class)s, %(route)s, 'Do something.', %(article)s,
            '2026-08-02', 'amended', %(label_en)s, 'Es tun', 'Etwas tun.', %(group)s, %(document)s)
"""
VALID = {
    "role": "provider",
    "risk_class": "high_risk",
    "route": None,
    "article": "art:16:a",
    "label_en": "Do it",
    "group": "build",
    "document": "art_9_risk_management",
}


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
            row.obligation.label_en,
            row.obligation.label_de,
            row.obligation.duty_de,
            row.obligation.group.value if row.obligation.group else None,
            row.obligation.document,
        )
        for row in table.rows()
    ]
    seeded = db.execute(
        "select obligation_key, role, risk_class, high_risk_route, article, applies_from,"
        " label_en, label_de, duty_de, duty_group, document"
        " from obligations where law_version = %s order by position",
        (table.law_version.value,),
    ).fetchall()
    assert seeded == expected
    assert all(row[6] and row[7] and row[8] for row in seeded)  # both labels, the German duty


def test_a_valid_row_is_accepted(db: psycopg.Connection) -> None:
    db.execute(INSERT, VALID)


def test_a_row_without_the_screens_texts_is_still_accepted(db: psycopg.Connection) -> None:
    """The C9 columns are nullable, so code that predates them (a shared local database, other
    branches) keeps inserting; the YAML loader and the seed tests require the texts instead."""
    db.execute(
        "insert into obligations (obligation_key, position, role, risk_class, duty, article,"
        " applies_from, law_version) values ('old-shape', 0, 'provider', 'high_risk',"
        " 'Do something.', 'art:16:a', '2026-08-02', 'amended')"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"route": "annex_iii", "risk_class": "limited_risk"},  # routes are for high-risk only
        {"article": "annex:III:4:a"},  # every row cites an article
        {"risk_class": "out_of_scope"},
        {"role": "authorised_representative"},
        {"route": "annex_ii"},
        {"label_en": ""},  # a label is never empty (C9)
        {"group": "later"},
        {"document": "Art 26 notice"},
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
