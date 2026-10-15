import pytest

from aiact.corpus.fetch import DEFAULT_MANIFEST, load_manifest
from aiact.corpus.sources import (
    LIBRARY,
    SOURCES,
    Source,
    _commission_pdf,  # pyright: ignore[reportPrivateUsage]
)

REQUIRED_DOCUMENTS = {
    "ai-act",
    "omnibus",
    "ai-act-consolidated",
    "guide-definition",
    "guide-prohibited",
    "guide-high-risk-general",
    "guide-high-risk-annex-i",
    "guide-high-risk-annex-iii",
    "guide-art50",
    "code-of-practice-transparency",
}


def test_registry_covers_every_corpus_document_in_en_and_de() -> None:
    keys = [(source.id, source.language) for source in SOURCES]
    assert len(keys) == len(set(keys))
    assert {doc_id for doc_id, _ in keys} == REQUIRED_DOCUMENTS
    for doc_id in REQUIRED_DOCUMENTS:
        assert (doc_id, "en") in keys and (doc_id, "de") in keys, doc_id


def test_every_english_version_has_a_url() -> None:
    assert all(source.url for source in SOURCES if source.language == "en")


def test_laws_are_eurlex_xhtml_from_cellar_in_the_right_language() -> None:
    laws = [s for s in SOURCES if s.status in ("law", "consolidated")]
    assert len(laws) == 6
    for law in laws:
        assert law.kind == "html"
        assert (law.url or "").startswith("https://publications.europa.eu/resource/celex/")
        assert law.source_page.startswith("https://eur-lex.europa.eu/")
        assert law.accept_language == {"en": "eng", "de": "deu"}[law.language]
        assert law.celex is not None and (law.url or "").endswith(law.celex)


def test_only_laws_carry_a_celex_number() -> None:
    guidance = [s for s in SOURCES if s.status in ("final", "draft")]
    assert guidance and all(s.celex is None for s in guidance)
    omnibus = {s.celex for s in SOURCES if s.id == "omnibus"}
    assert omnibus == {"32026R1744"}


def test_source_needs_exactly_one_of_url_and_reason() -> None:
    fields = {
        "id": "x",
        "language": "de",
        "title": "X",
        "kind": "pdf",
        "status": "final",
        "version": "2026-01-01",
        "source_page": "https://example.org",
    }
    with pytest.raises(ValueError):
        Source.model_validate(fields)
    with pytest.raises(ValueError):
        Source.model_validate(fields | {"url": "https://example.org/x", "absent_reason": "why"})


TITLES_DE = {
    "ai-act": "Verordnung (EU) 2024/1689 (KI-Verordnung)",
    "ai-act-consolidated": "KI-Verordnung, konsolidierte Fassung vom 27. Juli 2026",
    "omnibus": "Verordnung (EU) 2026/1744 (digitaler Omnibus zur KI)",
    "guide-definition": "Leitlinien der Kommission zur Definition eines KI-Systems",
    "guide-prohibited": (
        "Leitlinien der Kommission zu verbotenen Praktiken der künstlichen Intelligenz"
    ),
}
"""The German title of each text published in German (P7's wording, in the registry since P32)."""


def test_each_published_german_version_carries_its_german_title() -> None:
    titles = {s.id: s.title for s in SOURCES if s.language == "de" and s.url is not None}
    assert titles == TITLES_DE


def test_an_absent_german_version_keeps_the_english_title() -> None:
    english = {s.id: s.title for s in SOURCES if s.language == "en"}
    absent = [s for s in SOURCES if s.language == "de" and s.url is None]
    assert absent and all(s.title == english[s.id] for s in absent)


def test_the_committed_manifest_carries_the_registry_titles() -> None:
    """`data/manifest.yaml` is written by `aiact corpus fetch`; its titles are the registry's."""
    registry = {(s.id, s.language): s.title for s in SOURCES}
    manifest = {e.key: e.title for e in load_manifest(DEFAULT_MANIFEST).documents}
    assert manifest == registry


@pytest.mark.parametrize(("de", "title_de"), [(1, None), (None, "Leitlinien")])
def test_a_german_pdf_needs_a_german_title_and_only_then(
    de: int | None, title_de: str | None
) -> None:
    with pytest.raises(ValueError, match="German title"):
        _commission_pdf("x", "X", "final", "2026-01-01", LIBRARY, en=1, de=de, title_de=title_de)
