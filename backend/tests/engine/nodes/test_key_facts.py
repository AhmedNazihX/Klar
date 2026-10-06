"""The bound on the texts a model writes into an answer (E6's `MAX_TEXT_CHARS`, shared by E8):
checked when the reply is read, never sent in the JSON schema."""

import json

import pytest
from pydantic import BaseModel, ValidationError

from aiact.engine.nodes.facts import FACTS_RESPONSE_FORMAT, ExtractedFact
from aiact.engine.nodes.key_facts import MAX_TEXT_CHARS, KeyFact
from aiact.engine.nodes.role_obligations import ROLE_RESPONSE_FORMAT, ModificationFact, RoleFact
from aiact.schemas import FollowUpQuestion

AT_CAP, OVER = "x" * MAX_TEXT_CHARS, "x" * (MAX_TEXT_CHARS + 1)


def _fact(model: type[BaseModel], text: str) -> dict[str, object]:
    common = {"evidence": "inferred", "fact": text, "fact_numbers": []}
    answers: dict[type[BaseModel], dict[str, object]] = {
        KeyFact: {"answer": "yes", **common},
        ModificationFact: {"answer": "contested", **common},
        RoleFact: {"role": "deployer", **common},
    }
    return answers[model]


@pytest.mark.parametrize("model", [KeyFact, ModificationFact, RoleFact])
def test_a_fact_longer_than_the_cap_is_a_broken_answer(model: type[BaseModel]) -> None:
    assert model.model_validate(_fact(model, AT_CAP))
    with pytest.raises(ValidationError, match=f"longer than {MAX_TEXT_CHARS}"):
        model.model_validate(_fact(model, OVER))


@pytest.mark.parametrize(
    "texts",
    [{"text": OVER}, {"question": FollowUpQuestion(id="q", text=OVER)}],
    ids=["fact", "question"],
)
def test_an_extracted_fact_bounds_its_text_and_question(texts: dict[str, object]) -> None:
    given = {"text": "A fact", "evidence": "inferred", "quote": None, "question": None, **texts}
    with pytest.raises(ValidationError, match=f"longer than {MAX_TEXT_CHARS}"):
        ExtractedFact.model_validate(given)


def test_an_extracted_quote_is_not_bounded() -> None:
    """A quote must be found verbatim in the description, so it adds no prose of its own."""
    given = {"text": "A fact", "evidence": "stated", "quote": OVER, "question": None}
    assert ExtractedFact.model_validate(given).quote == OVER


@pytest.mark.parametrize("response_format", [FACTS_RESPONSE_FORMAT, ROLE_RESPONSE_FORMAT])
def test_the_bound_is_not_in_the_schema_sent_to_the_model(
    response_format: dict[str, object],
) -> None:
    assert "maxLength" not in json.dumps(response_format)
