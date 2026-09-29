"""`get_provision` (aiact/retrieval/provisions.py) against the local Supabase Postgres.

Most tests load their own documents (`test-c5-*` doc_keys) inside the `db` fixture's rolled-back
transaction and point the lookup at them, so they run on an empty database (CI). The texts are
Art. 4 (AI literacy) as published and as amended by the Omnibus from 2026-07-27. The last tests
read the loaded corpus and skip when it isn't there.
"""

from dataclasses import replace
from datetime import date

import psycopg
import pytest

from aiact.corpus.build import AI_ACT_IN_FORCE, DocumentLoad, DocumentRow, ProvisionRow
from aiact.corpus.load import load_all
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError, get_provision
from aiact.schemas import DISCLAIMER_DE, DISCLAIMER_EN, DocumentStatus, Language, LawVersion

pytestmark = pytest.mark.db

OMNIBUS_IN_FORCE = date(2026, 7, 27)
BEFORE_OMNIBUS = date(2025, 6, 1)
AFTER_OMNIBUS = date(2026, 9, 29)
KEYS = {LawVersion.ORIGINAL: "test-c5-act", LawVersion.AMENDED: "test-c5-act-consolidated"}

ART_4_OLD_EN = "Providers and deployers of AI systems shall take measures to ensure, to their best extent, a sufficient level of AI literacy of their staff."  # noqa: E501
ART_4_NEW_EN = "1. Providers and deployers of AI systems shall take measures to support the development of AI literacy of their staff."  # noqa: E501
ART_4_OLD_DE = "Die Anbieter und Betreiber von KI-Systemen ergreifen Maßnahmen, um nach besten Kräften sicherzustellen, dass ihr Personal über KI-Kompetenz verfügt."  # noqa: E501
ART_4_NEW_DE = "(1) Die Anbieter und Betreiber von KI-Systemen ergreifen Maßnahmen, um die Entwicklung der KI-Kompetenz ihres Personals zu unterstützen."  # noqa: E501
RECITAL_1 = "The purpose of this Regulation is to improve the functioning of the internal market."

ORIGINAL = DocumentRow(
    doc_key=KEYS[LawVersion.ORIGINAL],
    title="Test AI Act (original)",
    celex=None,
    doc_type="law",
    is_amending=False,
    status="final",
    law_version="original",
    language="en",
    published_on=date(2024, 7, 12),
    in_force_from=AI_ACT_IN_FORCE,
    source_url="https://eur-lex.europa.eu/",
    sha256="a" * 64,
)
AMENDED = replace(
    ORIGINAL,
    doc_key=KEYS[LawVersion.AMENDED],
    title="Test AI Act (consolidated)",
    status="consolidated",
    law_version="amended",
    published_on=OMNIBUS_IN_FORCE,
)
GUIDE = DocumentRow(
    doc_key="test-c5-guide",
    title="Test guideline",
    celex=None,
    doc_type="guideline",
    is_amending=False,
    status="draft",
    law_version=None,
    language="en",
    published_on=date(2026, 5, 19),
    in_force_from=None,
    source_url="https://ec.europa.eu/",
    sha256="b" * 64,
)
HEADING_EN, HEADING_DE = "Article 4 — AI literacy", "Artikel 4 — KI-Kompetenz"


def _original(language: str, heading: str, art_4: str) -> DocumentLoad:
    provisions = [ProvisionRow("art:4", None, None, heading, art_4, AI_ACT_IN_FORCE)]
    if language == "en":
        provisions.append(ProvisionRow("recital:1", None, None, None, RECITAL_1, AI_ACT_IN_FORCE))
    return DocumentLoad(replace(ORIGINAL, language=language), tuple(provisions))


def _amended(language: str, heading: str, old: str, new: str) -> DocumentLoad:
    return DocumentLoad(
        replace(AMENDED, language=language),
        (
            ProvisionRow("art:4", None, None, heading, old, AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE),
            ProvisionRow("art:4", None, None, heading, new, OMNIBUS_IN_FORCE),
        ),
    )


LOADS = (
    _original("en", HEADING_EN, ART_4_OLD_EN),
    _original("de", HEADING_DE, ART_4_OLD_DE),
    _amended("en", HEADING_EN, ART_4_OLD_EN, ART_4_NEW_EN),
    _amended("de", HEADING_DE, ART_4_OLD_DE, ART_4_NEW_DE),
    DocumentLoad(
        GUIDE,
        (
            ProvisionRow("guide:test-c5-guide:para:1", None, None, "I. Purpose", "(1) Guidance.",
                         GUIDE.published_on or AI_ACT_IN_FORCE),
            ProvisionRow("guide:test-c5-guide:ex:001", None, None, None, "A held-out example.",
                         GUIDE.published_on or AI_ACT_IN_FORCE, source_example_id="hr-ex-001",
                         is_held_out=True),
        ),
    ),
)  # fmt: skip


@pytest.fixture
def corpus(db: psycopg.Connection) -> psycopg.Connection:
    load_all(db, LOADS)
    return db


def _get(
    connection: psycopg.Connection,
    provision_id: str,
    language: Language | str = Language.EN,
    law_version: LawVersion | str | None = None,
    as_of: date | None = None,
    include_held_out: bool = False,
) -> Provision:
    return get_provision(
        provision_id,
        language,
        law_version,
        as_of,
        include_held_out=include_held_out,
        connection=connection,
        ai_act_doc_keys=KEYS,
    )


def test_the_amended_text_after_the_omnibus(corpus: psycopg.Connection):
    provision = _get(corpus, "art:4", as_of=AFTER_OMNIBUS)
    assert provision.text == ART_4_NEW_EN
    assert provision.law_version is LawVersion.AMENDED
    assert provision.doc_key == "test-c5-act-consolidated"
    assert provision.status is DocumentStatus.CONSOLIDATED
    assert (provision.valid_from, provision.valid_to) == (OMNIBUS_IN_FORCE, None)
    assert (provision.language, provision.english_only) == (Language.EN, False)
    assert provision.disclaimer == DISCLAIMER_EN


def test_the_amended_text_before_the_omnibus_is_the_old_slice(corpus: psycopg.Connection):
    provision = _get(corpus, "art:4", law_version="amended", as_of=BEFORE_OMNIBUS)
    assert provision.text == ART_4_OLD_EN
    assert provision.law_version is LawVersion.AMENDED
    assert (provision.valid_from, provision.valid_to) == (AI_ACT_IN_FORCE, OMNIBUS_IN_FORCE)


def test_the_boundary_day_already_has_the_new_text(corpus: psycopg.Connection):
    assert _get(corpus, "art:4", as_of=OMNIBUS_IN_FORCE).text == ART_4_NEW_EN


def test_the_original_text_is_an_explicit_view(corpus: psycopg.Connection):
    provision = _get(corpus, "art:4", law_version=LawVersion.ORIGINAL)
    assert provision.text == ART_4_OLD_EN
    assert provision.law_version is LawVersion.ORIGINAL
    assert provision.doc_key == "test-c5-act"
    assert provision.status is DocumentStatus.FINAL


def test_the_original_and_amended_german_texts(corpus: psycopg.Connection):
    original = _get(corpus, "art:4", language="de", law_version="original")
    amended = _get(corpus, "art:4", language=Language.DE, as_of=AFTER_OMNIBUS)
    assert (original.text, amended.text) == (ART_4_OLD_DE, ART_4_NEW_DE)
    assert {original.language, amended.language} == {Language.DE}
    assert not original.english_only
    assert not amended.english_only
    assert amended.disclaimer == DISCLAIMER_DE


def test_original_with_as_of_is_rejected(corpus: psycopg.Connection):
    with pytest.raises(ValueError, match="as_of resolves only against the amended text"):
        _get(corpus, "art:4", law_version="original", as_of=AFTER_OMNIBUS)


def test_a_guideline_in_english_only_falls_back_with_the_flag(corpus: psycopg.Connection):
    provision = _get(corpus, "guide:test-c5-guide:para:1", language="de", as_of=AFTER_OMNIBUS)
    assert provision.text == "(1) Guidance."
    assert (provision.language, provision.english_only) == (Language.EN, True)
    assert provision.law_version is None
    assert provision.status is DocumentStatus.DRAFT
    assert provision.disclaimer == DISCLAIMER_DE  # the notice follows the language asked for


def test_the_guideline_is_found_under_either_law_version(corpus: psycopg.Connection):
    original = _get(corpus, "guide:test-c5-guide:para:1", law_version="original")
    amended = _get(corpus, "guide:test-c5-guide:para:1", as_of=AFTER_OMNIBUS)
    assert original.text == amended.text == "(1) Guidance."


def test_a_guideline_before_its_publication_is_not_found(corpus: psycopg.Connection):
    with pytest.raises(ProvisionNotFoundError):
        _get(corpus, "guide:test-c5-guide:para:1", as_of=BEFORE_OMNIBUS)


def test_a_guideline_honours_as_of_under_the_original_version(corpus: psycopg.Connection):
    guide_id = "guide:test-c5-guide:para:1"
    provision = _get(corpus, guide_id, law_version="original", as_of=AFTER_OMNIBUS)
    assert provision.text == "(1) Guidance."
    assert provision.law_version is None
    with pytest.raises(ProvisionNotFoundError):
        _get(corpus, guide_id, law_version="original", as_of=BEFORE_OMNIBUS)


def test_a_held_out_example_is_not_retrievable_by_default(corpus: psycopg.Connection):
    with pytest.raises(ProvisionNotFoundError):
        _get(corpus, "guide:test-c5-guide:ex:001", as_of=AFTER_OMNIBUS)
    opted_in = _get(corpus, "guide:test-c5-guide:ex:001", as_of=AFTER_OMNIBUS,
                    include_held_out=True)  # fmt: skip
    assert opted_in.text == "A held-out example."


def test_a_recital_comes_from_the_original_text(corpus: psycopg.Connection):
    provision = _get(corpus, "recital:1", as_of=AFTER_OMNIBUS)
    assert provision.text == RECITAL_1
    assert provision.law_version is LawVersion.ORIGINAL


def test_a_recital_with_original_and_as_of_is_accepted(corpus: psycopg.Connection):
    provision = _get(corpus, "recital:1", law_version="original", as_of=BEFORE_OMNIBUS)
    assert provision.text == RECITAL_1
    assert provision.law_version is LawVersion.ORIGINAL


def test_a_missing_german_recital_falls_back_to_english(corpus: psycopg.Connection):
    provision = _get(corpus, "recital:1", language="de")
    assert (provision.language, provision.english_only) == (Language.EN, True)


def test_an_unknown_provision_is_not_found(corpus: psycopg.Connection):
    with pytest.raises(ProvisionNotFoundError, match="art:999"):
        _get(corpus, "art:999", as_of=AFTER_OMNIBUS)


def test_an_amending_act_is_never_returned(corpus: psycopg.Connection):
    omnibus = replace(AMENDED, doc_key="test-c5-omnibus", law_version=None, is_amending=True)
    entry_into_force = ProvisionRow("art:4", None, None, None, "In force.", OMNIBUS_IN_FORCE)
    load_all(corpus, (DocumentLoad(omnibus, (entry_into_force,)),))
    keys = {**KEYS, LawVersion.AMENDED: "test-c5-omnibus"}
    with pytest.raises(ProvisionNotFoundError):
        get_provision("art:4", as_of=AFTER_OMNIBUS, connection=corpus, ai_act_doc_keys=keys)


# --- The loaded corpus (skipped when `aiact corpus load` hasn't run) --------------------------


def _require_loaded_corpus(db: psycopg.Connection) -> None:
    loaded = db.execute(
        "select count(*) from documents where doc_key in ('ai-act', 'ai-act-consolidated')"
    ).fetchone()
    if loaded is None or loaded[0] < 4:
        pytest.skip("the corpus isn't loaded; run `aiact corpus load`")


def test_the_loaded_art_4_original_and_amended(db: psycopg.Connection):
    _require_loaded_corpus(db)
    original = get_provision("art:4", law_version="original", connection=db)
    before = get_provision("art:4", as_of=BEFORE_OMNIBUS, connection=db)
    after = get_provision("art:4", as_of=AFTER_OMNIBUS, connection=db)
    assert "to ensure, to their best extent" in original.text
    assert before.text == original.text
    assert "support the development of AI literacy" in after.text
    assert (original.doc_key, after.doc_key) == ("ai-act", "ai-act-consolidated")


def test_the_loaded_art_50_guidelines_are_english_only(db: psycopg.Connection):
    _require_loaded_corpus(db)
    provision = get_provision(
        "guide:guide-art50:para:1", language="de", as_of=AFTER_OMNIBUS, connection=db
    )
    assert (provision.language, provision.english_only) == (Language.EN, True)
    assert provision.doc_key == "guide-art50"
