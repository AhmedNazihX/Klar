"""The question shapes a model writes in its structured reply (E12).

They are the result contract's first `OpenQuestion` and `FollowUpQuestion`, kept as they were:
the JSON Schema a model call sends is built from them, and the recorded replies match on that
request, so their names, docstrings and fields must not change. The engine builds the
contract's richer shapes (structured readings, hints, answer options) from them; `as_contract`
turns a reply's question into the contract's, and the contract's `OpenQuestion` reads a reply's
plain readings as untitled ones.
"""

from pydantic import Field

from aiact.schemas import questions
from aiact.schemas.base import ContractModel
from aiact.schemas.questions import SLUG_PATTERN


class FollowUpQuestion(ContractModel):
    """A key-fact question. Its `id` keys the user's answer when the engine runs again."""

    id: str = Field(pattern=SLUG_PATTERN, description="Stable slug, for example `human_review`.")
    text: str = Field(min_length=1)
    about: str | None = Field(
        default=None, description="What the answer settles, for example a step or provision_id."
    )


class OpenQuestion(ContractModel):
    """A question the law and guidance don't settle, with both possible readings."""

    question: str = Field(min_length=1)
    # A variable-length tuple, so the JSON Schema uses minItems/maxItems rather than prefixItems.
    readings: tuple[str, ...] = Field(
        min_length=2, max_length=2, description="The two possible readings, stricter first."
    )


def as_contract(question: FollowUpQuestion) -> questions.FollowUpQuestion:
    """A question the model wrote, as the result carries it: answered in words (its form is the
    model's), with no hint, outcome or quote."""
    return questions.FollowUpQuestion(id=question.id, text=question.text, about=question.about)
