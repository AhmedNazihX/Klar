"""Saving an interview answer the way the Documents screen does (P9): an upsert on the four
columns of the unique key (P19), under the tool's id as P6 saves the tool (`systems.id`). The
composite foreign key to `systems` takes it for the user's own tool and refuses any other id.
"""

from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from tests.db.test_user_data_schema import _create_user, _one, _raises_sqlstate, as_user

pytestmark = pytest.mark.db

FOREIGN_KEY = "23503"
RESULT = {
    "risk_class": "limited_risk",
    "status": "decided",
    "law_version": "amended",
    "disclaimer": "Guidance only.",
}
SAVE_TOOL = "select save_classified_tool(null, 'AI inventory', 'Mood meter', 'Reads moods.', %s)"
SAVE_ANSWER = (
    "insert into interview_answers (system_id, template, question_key, answer)"
    " values (%s, 'art_50_3_disclosure', 'recognises', %s)"
    " on conflict (system_id, user_id, template, question_key)"
    " do update set answer = excluded.answer"
)
"""What `saveInterviewAnswer` sends through PostgREST (`onConflict` names all four columns)."""


def _tool(db: psycopg.Connection) -> UUID:
    """A tool saved as P6 saves it, as the current user: its id is `systems.id`."""
    return _one(db, SAVE_TOOL, (Jsonb(RESULT),))


def _answers(db: psycopg.Connection, tool: UUID) -> list[str]:
    rows = db.execute(
        "select answer from interview_answers where system_id = %s", (tool,)
    ).fetchall()
    return [row[0] for row in rows]


def test_an_answer_saves_under_the_users_own_tool_and_a_second_replaces_it(
    db: psycopg.Connection,
) -> None:
    user = _create_user(db)
    with as_user(db, user):
        tool = _tool(db)
        db.execute(SAVE_ANSWER, (tool, "emotion_recognition"))
        db.execute(SAVE_ANSWER, (tool, "both"))
        assert _answers(db, tool) == ["both"]


def test_an_answer_under_a_tool_id_the_inventory_never_saved_is_refused(
    db: psycopg.Connection,
) -> None:
    """The browser-only id P9 first used: no `systems` row, so the foreign key refuses it."""
    user = _create_user(db)
    with as_user(db, user), _raises_sqlstate(db, FOREIGN_KEY):
        db.execute(SAVE_ANSWER, (uuid4(), "both"))


def test_an_answer_under_another_users_tool_is_refused(db: psycopg.Connection) -> None:
    owner, other = _create_user(db), _create_user(db)
    with as_user(db, owner):
        tool = _tool(db)
    with as_user(db, other), _raises_sqlstate(db, FOREIGN_KEY):
        db.execute(SAVE_ANSWER, (tool, "both"))
    with as_user(db, owner):
        assert _answers(db, tool) == []
