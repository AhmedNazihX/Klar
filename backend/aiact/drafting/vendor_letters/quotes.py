"""The Act's text the prohibited message quotes: every Art. 5(1) point the result decided on,
read from the corpus by provision id, the result's law version and date, and the letter's
language, never taken from the posted result (decision 031).

A posted result is only checked against the contract, so its citations' quotes may have been
edited. The message names the points the result cites (the result's own finding) and quotes
each from the corpus; a point the corpus doesn't have at that version and date is no point of
Art. 5(1), and the message is refused (`UnknownPointError`). The corpus is behind `LawQuotes`:
the API reads it through `get_provision` (held-out examples hidden, untraced outside an engine
run), tests through the corpus built from `data/parsed/`.
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from aiact.drafting.vendor_letters.fills import deciding_points
from aiact.schemas import Citation, ClassificationResult, Language, LawVersion

MAX_POINTS = 10
"""Art. 5(1) lists ten points, (a) to (h) with (ba) and (bb): a result citing more distinct
points than that cites one the Act doesn't have, and is refused before any lookup."""


class LawQuotes(Protocol):
    """The corpus's text of provisions of the AI Act."""

    def __call__(
        self,
        provision_ids: Sequence[str],
        language: Language,
        law_version: LawVersion,
        as_of: date | None,
    ) -> tuple[Citation, ...]:
        """Each provision as a citation of its corpus text, in order: in `language` (English,
        marked `english_only`, when there is no German text), from `law_version` on `as_of`
        (None for the original text). Raises LookupError when one isn't in the corpus."""
        ...


class UnknownPointError(ValueError):
    """The result cites an Art. 5(1) point the corpus doesn't have at the result's law version
    and date."""


def quoted_points(
    result: ClassificationResult, language: Language, law_quotes: LawQuotes
) -> tuple[Citation, ...]:
    """The Art. 5(1) points a decided prohibited result decided on, quoted from the corpus in
    the letter's `language`; none, with no lookup, for any other result. Raises
    UnknownPointError when the result cites a point the corpus doesn't have."""
    points = deciding_points(result)
    if not points:
        return ()
    if len(points) > MAX_POINTS:
        raise UnknownPointError(f"{len(points)} points cited; Art. 5(1) has {MAX_POINTS}")
    # The original text has one slice per unit and takes no date (`get_provision`).
    as_of = None if result.law_version is LawVersion.ORIGINAL else result.as_of
    try:
        return law_quotes(points, language, result.law_version, as_of)
    except LookupError:
        raise UnknownPointError("a cited Art. 5(1) point is not in the corpus") from None
