import pytest

from aiact.eval.citation_index import CitationIndex, citation_checker
from aiact.schemas import Citation, Language, LawVersion

INDEX: CitationIndex = frozenset(
    {
        ("ai-act-consolidated", "art:6:3", "en", "amended"),
        ("ai-act", "art:6:3", "en", "original"),
        ("guide-high-risk-annex-iii", "guide:hr:ex:17", "en", None),
    }
)


def cite(
    document_id: str,
    provision_id: str = "art:6:3",
    law_version: LawVersion | None = LawVersion.AMENDED,
    language: Language = Language.EN,
) -> Citation:
    return Citation(
        provision_id=provision_id,
        document_id=document_id,
        law_version=law_version,
        language=language,
        quote="quoted text",
    )


@pytest.mark.parametrize(
    ("citation", "expected"),
    [
        (cite("ai-act-consolidated"), True),
        (cite("ai-act", law_version=LawVersion.ORIGINAL), True),
        (cite("made-up-document"), False),
        (cite("ai-act"), False),  # the corpus holds this document only as the original text
        (cite("ai-act-consolidated", law_version=LawVersion.ORIGINAL), False),
        (cite("ai-act-consolidated", language=Language.DE), False),
        (cite("ai-act-consolidated", "art:6:4"), False),
        (cite("guide-high-risk-annex-iii", "guide:hr:ex:17", law_version=None), True),
        (cite("ai-act-consolidated", law_version=None), True),  # no version: any held version
    ],
    ids=[
        "exact",
        "original-version",
        "made-up-document",
        "version-not-held",
        "wrong-version",
        "wrong-language",
        "unknown-provision",
        "guidance",
        "unversioned-citation",
    ],
)
def test_citation_resolves_on_document_provision_language_and_version(
    citation: Citation, expected: bool
) -> None:
    exists = citation_checker(INDEX)
    assert exists is not None
    assert exists(citation) is expected


def test_an_empty_corpus_gives_no_checker() -> None:
    assert citation_checker(frozenset()) is None
