"""Questions the interface asks the user; stable ids let answers be keyed across re-runs."""

from pydantic import Field

from aiact.schemas.base import ContractModel

SLUG_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
"""A short machine-readable id such as `ranks_people` or `citation_unverified`."""


class FollowUpQuestion(ContractModel):
    """A key-fact question. Its `id` keys the user's answer when the engine runs again."""

    id: str = Field(pattern=SLUG_PATTERN, description="Stable slug, for example `human_review`.")
    text: str = Field(min_length=1)
    about: str | None = Field(
        default=None, description="What the answer settles, for example a step or provision_id."
    )
