import pytest

from aiact.corpus.sources import SOURCES, Source

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
