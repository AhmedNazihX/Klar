"""The citation validator (aiact/engine/citations.py, E9) against the loaded corpus, through
`get_provision` and `get_omnibus_provision`; skipped when `aiact corpus load` hasn't run, and
failed instead in CI's isolation job, which loads the corpus and sets AIACT_REQUIRE_CORPUS.

It also checks that the in-memory corpus the replays use (`tests/engine/built_corpus.py`)
resolves citations exactly as the database does.
"""

from datetime import date

import psycopg
import pytest

from aiact.engine.citations import (
    CITATION_UNVERIFIED,
    CitationValidator,
    CorpusCitations,
    check_citations,
)
from aiact.engine.nodes.common import Lookup
from aiact.schemas import Citation, Language, LawVersion, Status
from tests.engine.built_corpus import built_corpus, omnibus_changes
from tests.engine.test_citations import ART_5_1_BA, FAKE, STATE, ScriptedNode, decided

pytestmark = pytest.mark.db

AFTER = date(2026, 12, 10)
BEFORE = date(2026, 3, 1)


def lookup(as_of: date | None, language: Language = Language.EN) -> Lookup:
    law_version = LawVersion.ORIGINAL if as_of is None else LawVersion.AMENDED
    return Lookup(
        language=language, law_version=law_version, as_of=as_of, exclude_source_example_ids=()
    )


def cite(
    provision_id: str,
    document_id: str,
    law_version: LawVersion | None,
    language: Language = Language.EN,
) -> Citation:
    return Citation(
        provision_id=provision_id,
        document_id=document_id,
        law_version=law_version,
        language=language,
        quote="As the node quoted it.",
    )


CASES = [
    (cite("art:5:1:ba", "ai-act-consolidated", LawVersion.AMENDED), lookup(AFTER)),
    (cite("art:5:1:ba", "ai-act-consolidated", LawVersion.AMENDED), lookup(BEFORE)),
    (cite("art:4", "ai-act", LawVersion.ORIGINAL), lookup(None)),
    (cite("art:4", "ai-act-consolidated", LawVersion.AMENDED), lookup(BEFORE)),
    (cite("art:4", "ai-act-consolidated", LawVersion.AMENDED, Language.DE), lookup(AFTER)),
    (cite("annex:III:4:a", "ai-act-consolidated", LawVersion.AMENDED), lookup(AFTER)),
    (cite("recital:27", "ai-act", LawVersion.ORIGINAL), lookup(AFTER)),
    (cite("art:1:1", "omnibus", None), lookup(AFTER)),
    (cite("art:1:1", "omnibus", None, Language.DE), lookup(BEFORE, Language.DE)),
    (cite("guide:guide-art50:para:1", "guide-art50", None), lookup(AFTER, Language.DE)),
    (cite("guide:guide-art50:para:1", "guide-art50", None, Language.DE), lookup(AFTER)),
    (
        cite("guide:guide-high-risk-annex-iii:ex:013", "guide-high-risk-annex-iii", None),
        lookup(AFTER),
    ),
    (
        cite("guide:guide-high-risk-annex-iii:ex:015", "guide-high-risk-annex-iii", None),
        lookup(AFTER),
    ),
    # The paragraph and point ids E16's citations fetch, and the replays' recordings hold.
    (cite("art:50:2", "ai-act-consolidated", LawVersion.AMENDED), lookup(AFTER)),
    (cite("art:5:1:bb", "ai-act-consolidated", LawVersion.AMENDED), lookup(AFTER)),
    (cite("art:2:1", "ai-act-consolidated", LawVersion.AMENDED), lookup(AFTER)),
    (cite("art:5:1:zz", "ai-act-consolidated", LawVersion.AMENDED), lookup(AFTER)),
]
"""Citations that resolve and that don't: each version, language, date and document kind."""


@pytest.mark.parametrize(("citation", "at"), CASES)
def test_the_built_corpus_resolves_as_the_database_does(
    corpus: psycopg.Connection, citation: Citation, at: Lookup
) -> None:
    from_db = check_citations((citation,), at, CorpusCitations(corpus), omnibus_changes())
    built = check_citations((citation,), at, built_corpus(), omnibus_changes())
    assert from_db == built


def test_the_loaded_art_5_1_ba_carries_the_marker_and_art_4_original_does_not(
    corpus: psycopg.Connection,
) -> None:
    source = CorpusCitations(corpus)
    (ba,) = check_citations(CASES[0][:1], lookup(AFTER), source, omnibus_changes()).verified
    (art_4,) = check_citations(CASES[2][:1], lookup(None), source, omnibus_changes()).verified
    assert ba.changed_by_omnibus
    assert not art_4.changed_by_omnibus


def test_a_loaded_omnibus_instruction_resolves(corpus: psycopg.Connection) -> None:
    citation = cite("art:1:1", "omnibus", None)
    checked = check_citations(
        (citation,), lookup(AFTER), CorpusCitations(corpus), omnibus_changes()
    )
    (verified,) = checked.verified
    assert "point (g) is replaced" in verified.quote


def test_the_default_validator_reads_the_database(corpus: psycopg.Connection) -> None:
    """No `source`: each check opens its own connection from DATABASE_URL (the production path),
    which tests/conftest.py points at the test database the `db` fixture uses."""
    node = ScriptedNode(decided(ART_5_1_BA, FAKE))
    step = CitationValidator(omnibus=omnibus_changes()).checked(node)(STATE).step
    assert node.calls == 2
    assert (step.status, step.error) == (Status.NEEDS_MORE_INFORMATION, CITATION_UNVERIFIED)
    (kept,) = step.citations
    assert (kept.provision_id, kept.changed_by_omnibus) == ("art:5:1:ba", True)
