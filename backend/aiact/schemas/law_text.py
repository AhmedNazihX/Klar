"""The label of the AI Act text a result relies on: its CELEX number and date (E12)."""

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from pydantic import Field

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import LawVersion


class LawText(ContractModel):
    """The AI Act text a result was checked against, as the screens label it ("the consolidated
    AI Act of 27 July 2026", CELEX 02024R1689-20260727)."""

    document_id: str = Field(
        min_length=1, description="The text's manifest `doc_key`, for example `ai-act`."
    )
    celex: str = Field(min_length=1, description="Its CELEX number on EUR-Lex.")
    version_date: date = Field(
        description="The original's publication date in the Official Journal, or the "
        "consolidation's cut-off date."
    )


LAW_TEXTS: Mapping[LawVersion, LawText] = MappingProxyType(
    {
        LawVersion.ORIGINAL: LawText(
            document_id="ai-act", celex="32024R1689", version_date=date(2024, 7, 12)
        ),
        LawVersion.AMENDED: LawText(
            document_id="ai-act-consolidated",
            celex="02024R1689-20260727",
            version_date=date(2026, 7, 27),
        ),
    }
)
"""The text of each law version, as fetched (`aiact.corpus.sources`; a test keeps them equal)."""
