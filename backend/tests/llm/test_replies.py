"""The question shapes a model writes (aiact/llm/replies.py, E12): their JSON Schema is part of
every recorded request that uses them, so it must stay exactly as the recordings were made."""

from aiact.llm import replies

OPEN_QUESTION_SCHEMA = {
    "additionalProperties": False,
    "description": "A question the law and guidance don't settle, with both possible readings.",
    "properties": {
        "question": {"minLength": 1, "title": "Question", "type": "string"},
        "readings": {
            "description": "The two possible readings, stricter first.",
            "items": {"type": "string"},
            "maxItems": 2,
            "minItems": 2,
            "title": "Readings",
            "type": "array",
        },
    },
    "required": ["question", "readings"],
    "title": "OpenQuestion",
    "type": "object",
}
FOLLOW_UP_QUESTION_SCHEMA = {
    "additionalProperties": False,
    "description": "A key-fact question. Its `id` keys the user's answer when the engine runs "
    "again.",
    "properties": {
        "id": {
            "description": "Stable slug, for example `human_review`.",
            "pattern": "^[a-z][a-z0-9_]{0,63}$",
            "title": "Id",
            "type": "string",
        },
        "text": {"minLength": 1, "title": "Text", "type": "string"},
        "about": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": "What the answer settles, for example a step or provision_id.",
            "title": "About",
        },
    },
    "required": ["id", "text"],
    "title": "FollowUpQuestion",
    "type": "object",
}


def test_the_open_question_a_model_writes_is_unchanged() -> None:
    assert replies.OpenQuestion.model_json_schema() == OPEN_QUESTION_SCHEMA


def test_the_follow_up_question_a_model_writes_is_unchanged() -> None:
    assert replies.FollowUpQuestion.model_json_schema() == FOLLOW_UP_QUESTION_SCHEMA


def test_a_models_question_reaches_the_result_answered_in_words() -> None:
    reply = replies.FollowUpQuestion(id="output_use", text="Who reads it?", about="high_risk")
    question = replies.as_contract(reply)
    assert (question.id, question.text, question.about) == (
        "output_use",
        "Who reads it?",
        "high_risk",
    )
    assert (question.hint, question.options, question.if_yes, question.citations) == (
        None,
        (),
        None,
        (),
    )
