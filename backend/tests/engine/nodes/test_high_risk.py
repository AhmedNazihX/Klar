"""The high-risk node (E5): Art. 6 applied to invented answers, the retrieval it runs (the
exclude filter, the German fallback, the candidates), the model call with a fake model, and the
replays of INIT's worked example and the Annex I own cases.

The unit-test descriptions and answers are invented, not benchmark cases. The replays read the
own cases from `eval/cases/own/e/` and replay recorded model answers; the corpus answers the
recording run saw are stored next to each cassette (`<cassette>.corpus.json`), so a replay needs
neither the database nor the network.
"""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date
from typing import cast

import psycopg
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field, SecretStr

from aiact.db import connect
from aiact.engine.citations import with_checked_citations
from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes import corpus as corpus_module
from aiact.engine.nodes import high_risk as node
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.high_risk import (
    HighRiskCheck,
    HighRiskOutputError,
    Settled,
    annex_i_facts,
    law_title,
    to_outcome,
)
from aiact.engine.nodes.high_risk_answer import (
    AnnexIAnswer,
    AnnexIIIAnswer,
    Art63Answer,
    Art63Condition,
    HighRiskAnswer,
)
from aiact.engine.nodes.high_risk_retrieval import (
    ANNEX_III_POINTS,
    HighRiskCorpus,
    HighRiskLibrary,
    Retrieved,
    retrieve,
)
from aiact.engine.nodes.high_risk_texts import TEXTS, annex_i_entry, version_words
from aiact.engine.nodes.key_facts import Answer
from aiact.engine.nodes.open_in_law import NOT_NAMED, open_field
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import (
    EXEMPTION_TRAP,
    case_label,
    high_risk_matches,
    high_risk_or_exempt_matches,
    replay_state,
)
from aiact.eval.experiments.matchers import WORKED_EXAMPLE as WORKED_EXAMPLE_CASE
from aiact.llm import LLMConfigError, OpenRouterEmbeddings
from aiact.llm.replies import FollowUpQuestion as ReplyQuestion
from aiact.llm.replies import OpenQuestion
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    YES_NO,
    AnswerOutcome,
    DocumentStatus,
    EvidenceTag,
    HighRiskRoute,
    Language,
    LawVersion,
    RiskClass,
    SettledByKind,
    Status,
    StepName,
)
from aiact.settings import Settings
from tests.conftest import REFUSAL_ROUTE
from tests.engine.built_corpus import (
    built_validator,
    unresolved_citations,
    whole_articles,
)
from tests.engine.nodes.corpus_recording import (
    CorpusRecording,
    corpus_recording,
    lookup_call,
    require_recording,
)
from tests.engine.nodes.known_gaps import (
    NOT_ASSESSED,
    KnownGap,
    expect_known_gap,
    negative_cases,
)
from tests.engine.nodes.pinned import assert_pinned_route

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
AS_OF = date(2026, 9, 30)
WORKED_EXAMPLE = WORKED_EXAMPLE_CASE.description
PUMP_TOOL = "We make an app that plans pump maintenance for a water utility."
EXCLUDED = ("hr-ex-900", "hr-ex-901")

ANNEX_I_TEXT = {
    "annex:I:A:6": "6. Directive 2014/53/EU of the European Parliament and of the Council of 16 "
    "April 2014 on the harmonisation of the laws of the Member States relating to the making "
    "available on the market of radio equipment and repealing Directive 1999/5/EC (OJ L 153);",
    "annex:I:A:11": "11. Regulation (EU) 2017/745 of the European Parliament and of the Council "
    "of 5 April 2017 on medical devices, amending Directive 2001/83/EC (OJ L 117);",
    "annex:I:B:21": "21. Regulation (EU) 2023/1230 of the European Parliament and of the Council "
    "of 14 June 2023 on machinery and repealing Directive 2006/42/EC (OJ L 165);",
}
ORIGINAL_ANNEX_I_TEXT = {
    "annex:I:A:1": "1. Directive 2006/42/EC of the European Parliament and of the Council of 17 "
    "May 2006 on machinery, and amending Directive 95/16/EC (OJ L 157, 9.6.2006, p. 24);",
    "annex:I:A:11": ANNEX_I_TEXT["annex:I:A:11"],
    "annex:I:B:19": "19. Regulation (EU) 2019/2144 of the European Parliament and of the Council "
    "of 27 November 2019 on type-approval requirements for motor vehicles and their trailers "
    "(OJ L 325);",
}
"""The original text: machinery is still in Section A (point 1), and Section B ends at 20."""
DE_ANNEX_I_TEXT = {
    "annex:I:A:11": "11. Verordnung (EU) 2017/745 des Europäischen Parlaments und des Rates vom 5. "
    "April 2017 über Medizinprodukte, zur Änderung der Richtlinie 2001/83/EG (ABl. L 117);",
}


# --- Fakes ---------------------------------------------------------------------------------------


def provision(
    pid: str,
    text: str | None = None,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
) -> Provision:
    is_original = law_version is LawVersion.ORIGINAL
    return Provision(
        provision_id=pid,
        doc_key="ai-act" if is_original else "ai-act-consolidated",
        document_title="AI Act" if is_original else "AI Act (consolidated)",
        doc_type="law",
        law_version=law_version,
        status=DocumentStatus.FINAL if is_original else DocumentStatus.CONSOLIDATED,
        language=language,
        english_only=False,
        heading=None,
        text=text or f"Text of {pid}.",
        valid_from=date(2024, 8, 1) if is_original else date(2026, 7, 27),
        valid_to=None,
        disclaimer=DISCLAIMER[language],
    )


def fake_lookup(
    provision_id: str, language: Language, law_version: LawVersion, as_of: date | None
) -> Provision:
    """Any art/annex id has a text; the Annex I points in the tables have their real titles (the
    original text's for `original`)."""
    table = (
        DE_ANNEX_I_TEXT
        if language is Language.DE
        else ORIGINAL_ANNEX_I_TEXT
        if law_version is LawVersion.ORIGINAL
        else ANNEX_I_TEXT
    )
    if provision_id.startswith("annex:I:") and provision_id not in table:
        raise ProvisionNotFoundError(provision_id)
    return provision(provision_id, table.get(provision_id), language, law_version)


def hit(pid: str, language: Language = Language.EN) -> SearchHit:
    is_guidance = pid.startswith("guide:")
    return SearchHit(
        provision_id=pid,
        doc_key=pid.split(":")[1] if is_guidance else "ai-act-consolidated",
        document_title="A document",
        doc_type="guideline" if is_guidance else "law",
        law_version=None if is_guidance else LawVersion.AMENDED,
        status=DocumentStatus.DRAFT if is_guidance else DocumentStatus.CONSOLIDATED,
        language=language,
        heading="A heading",
        text=f"Text of {pid}.",
        valid_from=date(2026, 5, 19),
        valid_to=None,
        score=0.03,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.6,
        keyword_idf=None,
    )


EXAMPLE = "guide:guide-high-risk-annex-iii:ex:042"
GUIDE_HITS = (hit(EXAMPLE), hit("guide:guide-high-risk-annex-iii:para:010"))


class FakeSearch:
    """Records every call; returns `guidance[language]` for the guidelines searched."""

    def __init__(self, guidance: dict[Language, Sequence[SearchHit]] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._guidance = guidance if guidance is not None else {Language.EN: GUIDE_HITS}

    def __call__(
        self,
        query: str,
        language: Language,
        law_version: LawVersion,
        as_of: date | None,
        **kwargs: object,
    ) -> SearchResults:
        self.calls.append(
            {"query": query, "language": language, "law_version": law_version, **kwargs}
        )
        assert kwargs["doc_types"] == {"guideline"}  # the law is looked up, never searched
        hits = tuple(self._guidance.get(language, ()))
        return SearchResults(
            query=query,
            language=language,
            law_version=law_version,
            as_of=as_of,
            hits=hits,
            max_distance=None,
            found=bool(hits),
            disclaimer=DISCLAIMER[language],
        )


class FakeLibrary:
    """A `HighRiskLibrary` over `FakeSearch` and `fake_lookup`: each search reaches `searches`
    with the run's lookup spelled out, as `HighRiskCorpus` hands it to `search_ai_act`."""

    def __init__(self, searches: FakeSearch | None = None) -> None:
        self.searches = searches or FakeSearch()

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        return fake_lookup(provision_id, lookup.language, lookup.law_version, lookup.as_of)

    def search(
        self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
    ) -> tuple[SearchHit, ...]:
        found = self.searches(
            query,
            language,
            lookup.law_version,
            lookup.as_of,
            doc_types={doc_type},
            exclude_source_example_ids=lookup.exclude_source_example_ids,
            limit=limit,
        )
        return found.hits


def state(
    description: str = WORKED_EXAMPLE,
    language: Language = Language.EN,
    exclude: tuple[str, ...] = (),
    law_version: LawVersion = LawVersion.AMENDED,
) -> EngineState:
    return {
        "description": description,
        "language": language,
        "law_version": law_version,
        "as_of": AS_OF,
        "exclude_source_example_ids": exclude,
        "facts": (),
        "steps": (),
    }


def retrieved(
    language: Language = Language.EN, law_version: LawVersion = LawVersion.AMENDED
) -> Retrieved:
    return retrieve(state(language=language, law_version=law_version), FakeLibrary())


# --- Answers -------------------------------------------------------------------------------------


def _openness(open_question: OpenQuestion | None) -> dict[str, object]:
    """A route's `settled_in_law` and `open_question`: settled unless a question is given."""
    settled = Settled.YES if open_question is None else Settled.NO
    return {"settled_in_law": settled, "open_question": open_question}


def annex_iii(
    point: str | None = None,
    uses: Answer = Answer.NO,
    public_authority: Answer = Answer.NO,
    examples: tuple[str, ...] = (),
    open_question: OpenQuestion | None = None,
    on: str = NOT_NAMED,
) -> AnnexIIIAnswer:
    """`on` is the key fact an open question is about (`open_on`)."""
    return AnnexIIIAnswer.model_validate(
        {
            "point": point,
            "uses": uses,
            "public_authority": public_authority,
            **_openness(open_question),
            "open_on": on,
            "evidence": EvidenceTag.INFERRED,
            "fact": f"Annex III: {point or 'none'}",
            "fact_numbers": (),
            "examples": examples,
        }
    )


def art_6_3(
    condition: Art63Condition = Art63Condition.NONE,
    profiling: Answer = Answer.NO,
    open_question: OpenQuestion | None = None,
) -> Art63Answer:
    return Art63Answer.model_validate(
        {
            "condition": condition,
            "profiling": profiling,
            **_openness(open_question),
            "evidence": EvidenceTag.INFERRED,
            "fact": f"Art. 6(3): {condition.value}, profiling {profiling.value}",
            "fact_numbers": (),
        }
    )


def annex_i(
    point: str | None = None,
    covered: Answer = Answer.NO,
    safety: Answer = Answer.NO,
    third_party: Answer = Answer.NO,
    open_question: OpenQuestion | None = None,
    on: str = NOT_NAMED,
) -> AnnexIAnswer:
    """`on` is the key fact an open question is about (`open_on`)."""
    return AnnexIAnswer.model_validate(
        {
            "point": point,
            "covered": covered,
            "safety_component_or_product": safety,
            "third_party_assessment": third_party,
            **_openness(open_question),
            "open_on": on,
            "evidence": EvidenceTag.INFERRED,
            "fact": f"Annex I: {point or 'none'}",
            "fact_numbers": (),
        }
    )


def answer(
    iii: AnnexIIIAnswer | None = None,
    art63: Art63Answer | None = None,
    one: AnnexIAnswer | None = None,
    question: ReplyQuestion | None = None,
) -> HighRiskAnswer:
    return HighRiskAnswer(
        annex_iii=iii or annex_iii(),
        art_6_3=art63 or art_6_3(),
        annex_i=one or annex_i(),
        question=question,
    )


YES = Answer.YES
RANKS_APPLICANTS = annex_iii("annex:III:4:a", YES)
MEDICAL_DEVICE = annex_i("annex:I:A:11", YES, YES, YES)


def outcome(
    given: HighRiskAnswer,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
) -> CheckOutcome:
    at = state(language=language, law_version=law_version)
    return to_outcome(given, at, retrieved(language, law_version), FakeLibrary())


def cited(result: CheckOutcome) -> list[str]:
    return [citation.provision_id for citation in result.step.citations]


def question_ids(result: CheckOutcome) -> list[str]:
    return [question.id for question in result.follow_up_questions]


# --- Annex III and the Art. 6(3) filter ----------------------------------------------------------


def test_profiling_keeps_an_annex_iii_use_high_risk() -> None:
    result = outcome(answer(RANKS_APPLICANTS, art_6_3(Art63Condition.D, profiling=YES)))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.annex_point == "annex:III:4:a"
    assert not result.annex_iii_exempt
    assert result.step.status is Status.DECIDED
    assert "profiles natural persons" in result.step.decision
    assert "Annex III point 4(a)" in result.step.decision
    assert {"annex:III:4:a", "art:6:2", "art:6:3"} <= set(cited(result))
    assert not {"art:6:3:d", "art:6:4"} & set(cited(result))  # profiling blocks the exemption


def test_no_art_6_3_condition_means_high_risk() -> None:
    result = outcome(answer(RANKS_APPLICANTS))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert "None of the Art. 6(3) conditions applies" in result.step.decision


def test_a_condition_without_profiling_exempts_under_art_6_3() -> None:
    result = outcome(answer(RANKS_APPLICANTS, art_6_3(Art63Condition.A, profiling=Answer.NO)))
    assert result.high_risk_route is None
    assert result.annex_iii_exempt
    assert result.annex_point is None  # set only for a high-risk finding
    assert result.step.status is Status.DECIDED
    assert {"art:6:3:a", "art:6:4"} <= set(cited(result))
    assert "Art. 6(3)(a)" in result.step.decision
    assert "Annex III point 4(a)" in result.step.decision


def test_unknown_profiling_under_a_condition_assumes_high_risk_and_asks() -> None:
    result = outcome(answer(RANKS_APPLICANTS, art_6_3(Art63Condition.B, Answer.UNKNOWN)))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "profiling"
    assert question_ids(result)[0] == "profiling"
    assert "Assumed high-risk on the Annex III route" in result.step.decision
    assert {"art:6:3:b", "art:6:4"} <= set(cited(result))  # the exemption may still apply


def test_a_benefits_scheme_of_unknown_owner_asks_whether_it_is_public() -> None:
    iii = annex_iii("annex:III:5:a", YES, public_authority=Answer.UNKNOWN)
    result = outcome(answer(iii))
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "public_scheme"
    assert result.high_risk_route is HighRiskRoute.ANNEX_III


def test_a_private_benefits_scheme_is_not_annex_iii_5a() -> None:
    result = outcome(answer(annex_iii("annex:III:5:a", YES, public_authority=Answer.NO)))
    assert result.high_risk_route is None
    assert not result.annex_iii_exempt
    assert result.step.status is Status.DECIDED


def test_a_border_use_states_the_authority_as_an_assumed_fact() -> None:
    iii = annex_iii("annex:III:7:b", YES, public_authority=Answer.UNKNOWN)
    result = outcome(answer(iii))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.step.status is Status.DECIDED
    assumed = [f for f in result.step.facts_used if f.evidence is EvidenceTag.ASSUMED]
    assert [f.text for f in assumed] == [node.AUTHORITY_ASSUMED[Language.EN]]
    assert "public_authority_user" in question_ids(result)
    [confirm] = [q for q in result.follow_up_questions if q.id == "public_authority_user"]
    assert confirm.about == "annex:III:7"


def test_a_law_enforcement_use_asks_its_confirmation_about_point_6() -> None:
    result = outcome(answer(annex_iii("annex:III:6:d", YES, public_authority=Answer.UNKNOWN)))
    [confirm] = [q for q in result.follow_up_questions if q.id == "public_authority_user"]
    assert confirm.about == "annex:III:6"


def test_an_open_scholarship_decision_asks_whether_it_decides_admission() -> None:
    result = outcome(answer(annex_iii("annex:III:3:a", Answer.UNKNOWN)))
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "decides_admission"


def test_the_models_own_question_replaces_the_generic_one() -> None:
    own = ReplyQuestion(id="output_use", text="Who reads the score?", about="high_risk")
    result = outcome(answer(annex_iii("annex:III:4:b", Answer.UNKNOWN), question=own))
    missing = result.step.missing_fact
    assert missing is not None
    assert (missing.id, missing.text, missing.about) == (own.id, own.text, own.about)
    assert missing.options == ()  # the model's question is answered in words
    assert missing.hint == "The answer decides whether the system is high-risk (Art. 6(2))."
    assert [c.provision_id for c in missing.citations] == ["annex:III:4:b"]
    assert "annex_iii_use" not in question_ids(result)
    assert "Who reads the score?" in result.step.decision


def test_an_unlisted_point_is_a_broken_output() -> None:
    with pytest.raises(HighRiskOutputError, match=r"annex_iii\.point") as raised:
        outcome(answer(annex_iii("annex:III:9", YES)))
    assert "annex:III:9" not in str(raised.value)  # the field is named, not the model's value


# --- Annex I -------------------------------------------------------------------------------------


def test_a_certified_medical_device_is_high_risk_on_the_annex_i_route() -> None:
    result = outcome(answer(one=MEDICAL_DEVICE))
    assert result.high_risk_route is HighRiskRoute.ANNEX_I
    assert result.annex_point == "annex:I:A:11"
    assert result.step.status is Status.DECIDED
    assert "Regulation (EU) 2017/745 on medical devices" in result.step.decision
    assert "Annex I Section A point 11" in result.step.decision
    assert {"annex:I:A:11", "art:6:1"} <= set(cited(result))
    assert "art:2:2" not in cited(result)


def test_a_section_b_product_leaves_the_duties_to_the_sector_law() -> None:
    result = outcome(answer(one=annex_i("annex:I:B:21", YES, YES, YES)))
    assert result.high_risk_route is HighRiskRoute.ANNEX_I
    assert result.annex_point == "annex:I:B:21"
    assert "Art. 2(2)" in result.step.decision
    assert "Regulation (EU) 2023/1230 on machinery" in result.step.decision
    assert "art:2:2" in cited(result)


def test_an_open_conformity_route_names_the_law_and_asks_the_decisive_question() -> None:
    result = outcome(answer(one=annex_i("annex:I:B:21", YES, YES, Answer.UNKNOWN)))
    assert result.high_risk_route is HighRiskRoute.ANNEX_I
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    missing = result.step.missing_fact
    assert missing is not None
    assert missing.id == "third_party_assessment"
    assert "Regulation (EU) 2023/1230 on machinery" in missing.text
    assert missing.text in result.step.decision


def test_an_open_intended_purpose_is_asked_before_the_rest() -> None:
    result = outcome(answer(one=annex_i("annex:I:A:11", Answer.UNKNOWN, YES, YES)))
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "intended_purpose"


def test_a_radio_only_notified_body_does_not_meet_art_6_1_b() -> None:
    result = outcome(answer(one=annex_i("annex:I:A:6", YES, YES, Answer.NO)))
    assert result.high_risk_route is None
    assert result.step.status is Status.DECIDED
    assert "Directive 2014/53/EU on radio equipment" in result.step.decision
    assert "third-party conformity assessment" in result.step.decision


def test_a_service_efficiency_tool_is_not_a_safety_component() -> None:
    result = outcome(answer(one=annex_i("annex:I:A:11", YES, Answer.NO, YES)))
    assert result.high_risk_route is None
    assert "not a safety component" in result.step.decision


def test_a_malformed_annex_i_point_is_named_by_field_only() -> None:
    with pytest.raises(
        HighRiskOutputError, match=r"annex_i\.point is not an Annex I point"
    ) as raised:
        outcome(answer(one=annex_i("annex:I:C:99", YES, YES, YES)))
    assert "annex:I:C:99" not in str(raised.value)


def test_an_annex_i_point_without_a_text_is_a_broken_output() -> None:
    with pytest.raises(HighRiskOutputError, match=r"annex_i\.point") as raised:
        outcome(answer(one=annex_i("annex:I:A:1", YES, YES, YES)))
    assert "annex:I:A:1" not in str(raised.value)


def test_both_routes_prefer_annex_iii_and_explain_both() -> None:
    result = outcome(answer(annex_iii("annex:III:5:d", YES), art_6_3(), MEDICAL_DEVICE))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.annex_point == "annex:III:5:d"
    assert "Annex III point 5(d)" in result.step.decision
    assert "Regulation (EU) 2017/745 on medical devices" in result.step.decision
    assert {"annex:III:5:d", "annex:I:A:11"} <= set(cited(result))


# --- Ambiguity, no match, language ---------------------------------------------------------------

OPEN = OpenQuestion(
    question="Does the in-house exemption count as no third-party assessment?",
    readings=("High-risk: the device class needs a notified body.", "Not high-risk."),
)


def assert_ambiguous(result: CheckOutcome, route: HighRiskRoute) -> None:
    assert result.high_risk_route is route
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    question = result.step.open_question
    assert question is not None
    assert question.question == OPEN.question
    assert tuple(reading.explanation for reading in question.readings) == OPEN.readings
    assert result.step.missing_fact is None
    assert "pending legal review" in result.step.decision


def test_an_open_annex_i_route_is_ambiguous_even_when_its_facts_all_read_yes() -> None:
    result = outcome(answer(one=annex_i("annex:I:A:11", YES, YES, YES, open_question=OPEN)))
    assert_ambiguous(result, HighRiskRoute.ANNEX_I)
    assert result.annex_point == "annex:I:A:11"


ANNEX_I_FACTS = ("covered", "safety_component_or_product", "third_party_assessment")
ANNEX_I_RULED_OUT = [
    pytest.param((Answer.NO, YES, YES), 0, id="not-covered"),
    pytest.param((YES, Answer.NO, YES), 1, id="not-a-safety-component"),
    pytest.param((YES, YES, Answer.NO), 2, id="no-third-party-assessment"),
]
"""The Art. 6(1) facts with one answered "no", and which one."""


@pytest.mark.parametrize(("facts", "against"), ANNEX_I_RULED_OUT)
def test_an_annex_i_route_another_fact_rules_out_is_not_held_open(
    facts: tuple[Answer, Answer, Answer], against: int
) -> None:
    """B3: the Art. 6(1) facts are cumulative, so with the open question on another of them, one
    settled "no" settles the route as not met."""
    other = ANNEX_I_FACTS[(against + 1) % len(ANNEX_I_FACTS)]
    one = annex_i("annex:I:A:11", *facts, open_question=OPEN, on=other)
    result = outcome(answer(one=one))
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is None
    assert result.step.open_question is None


@pytest.mark.parametrize(("facts", "against"), ANNEX_I_RULED_OUT)
def test_an_annex_i_facts_own_lenient_answer_never_settles_its_open_question(
    facts: tuple[Answer, Answer, Answer], against: int
) -> None:
    """B2: the in-house pattern, whether an exemption from the sector law's third-party
    assessment means Art. 6(1)(b) is not met, is open in law; the model answers the fact "no",
    as the description states it, and code reads it on its stricter side, so high-risk stays
    the working assumption."""
    one = annex_i("annex:I:A:11", *facts, open_question=OPEN, on=ANNEX_I_FACTS[against])
    result = outcome(answer(one=one))
    assert_ambiguous(result, HighRiskRoute.ANNEX_I)
    assert result.annex_point == "annex:I:A:11"


@pytest.mark.parametrize(
    ("facts", "is_open"),
    [
        pytest.param((Answer.NO, YES, YES), False, id="not-covered"),
        pytest.param((YES, Answer.NO, YES), True, id="not-a-safety-component"),
        pytest.param((YES, YES, Answer.NO), True, id="no-third-party-assessment"),
    ],
)
def test_an_annex_i_question_that_names_no_fact_stays_open_once_raised(
    facts: tuple[Answer, Answer, Answer], is_open: bool
) -> None:
    """R1: `covered` is the route's gate, so answered "no" and not the fact held open, the route
    is not raised, whatever `settled_in_law` says. A raised route left unsettled without
    naming its open fact stays open: any other "no" may be the question's lenient side."""
    result = outcome(answer(one=annex_i("annex:I:A:11", *facts, open_question=OPEN)))
    if is_open:
        assert_ambiguous(result, HighRiskRoute.ANNEX_I)
        return
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is None
    assert result.step.open_question is None


def test_an_open_annex_iii_point_is_ambiguous_with_high_risk_assumed() -> None:
    iii = annex_iii("annex:III:4:a", YES, open_question=OPEN)
    result = outcome(answer(iii))
    assert_ambiguous(result, HighRiskRoute.ANNEX_III)
    assert {"annex:III:4:a", "art:6:2", "art:6:3"} <= set(cited(result))


ANNEX_III_RULED_OUT = [
    pytest.param("annex:III:5:a", Answer.NO, YES, "uses", id="use-no"),
    pytest.param("annex:III:5:a", YES, Answer.NO, "public_authority", id="public-user-no"),
]
"""A point with its use or the user it names answered "no", and which fact that is."""


@pytest.mark.parametrize(("point", "uses", "user", "against"), ANNEX_III_RULED_OUT)
def test_an_annex_iii_point_another_fact_rules_out_is_not_held_open(
    point: str, uses: Answer, user: Answer, against: str
) -> None:
    """H1 and B3: a point applies to its listed use and the user it names; with the open
    question on the other of them, the one settled "no" rules the point out, and an open Art.
    6(3) question on it is moot."""
    other = "public_authority" if against == "uses" else "uses"
    iii = annex_iii(point, uses, user, open_question=OPEN, on=other)
    result = outcome(answer(iii, art_6_3(Art63Condition.D, open_question=OPEN)))
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is None
    assert not result.annex_iii_exempt
    assert result.step.open_question is None


@pytest.mark.parametrize(("point", "uses", "user", "against"), ANNEX_III_RULED_OUT)
def test_an_annex_iii_facts_own_lenient_answer_never_settles_its_open_question(
    point: str, uses: Answer, user: Answer, against: str
) -> None:
    """B2 and B3: open on the use, or on whether a public authority uses it (or someone acting
    on its behalf), the model's "no" to that fact decides nothing: code reads it on its
    stricter side, and the point stays open with high-risk assumed."""
    iii = annex_iii(point, uses, user, open_question=OPEN, on=against)
    result = outcome(answer(iii))
    assert_ambiguous(result, HighRiskRoute.ANNEX_III)
    assert result.annex_point == point


def test_an_open_exemption_on_a_point_whose_user_is_open_stays_open() -> None:
    """B3 for Art. 6(3) (H2): an open exemption is not dropped because the model answered the
    user it is itself unsure of "no"; the user held strict lists the point, and the open
    exemption keeps high-risk as the working assumption."""
    iii = annex_iii("annex:III:5:a", YES, Answer.NO, open_question=OPEN, on="public_authority")
    result = outcome(answer(iii, art_6_3(Art63Condition.D, open_question=OPEN)))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    assert not result.annex_iii_exempt


# --- E19 decision 1: an open listing is moot once Art. 6(3) settles the exemption ----------------

LISTING_OPEN = annex_iii("annex:III:4:b", YES, open_question=OPEN, on="uses")
"""4(b) open in law on whether it lists the use, the model's own answer to it either way."""
EXEMPT_C = art_6_3(Art63Condition.C)
"""Art. 6(3)(c) met, no profiling, both settled in law."""


@pytest.mark.parametrize("uses", [YES, Answer.NO], ids=["uses-yes", "uses-no"])
def test_an_open_listing_with_a_settled_exemption_is_exempt_and_asks_the_listing(
    uses: Answer,
) -> None:
    """Either reading of the listing gives "not high-risk" (unlisted, or listed and exempt), so
    the open question is moot: the existing exempt path for an unknown listing, which still
    asks it, since the Art. 6(4) duty depends on it."""
    listing = annex_iii("annex:III:4:b", uses, open_question=OPEN, on="uses")
    result = outcome(answer(listing, EXEMPT_C))
    assert result.high_risk_route is None
    assert result.annex_iii_exempt
    assert result.step.open_question is None
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "annex_iii_use"
    assert result.step.missing_fact.if_yes is None  # a yes keeps it exempt, not high-risk
    assert {"annex:III:4:b", "art:6:3:c", "art:6:4"} <= set(cited(result))
    assert "Assumed exempt under Art. 6(3) until this is answered" in result.step.decision


def test_an_open_user_with_a_settled_exemption_asks_the_users_question() -> None:
    """The same for a point that names its user, open on `public_authority`: 5(a) asks whether
    the scheme is public."""
    listing = annex_iii("annex:III:5:a", YES, Answer.NO, open_question=OPEN, on="public_authority")
    result = outcome(answer(listing, art_6_3(Art63Condition.D)))
    assert result.annex_iii_exempt
    assert result.high_risk_route is None
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "public_scheme"


def test_an_open_admission_listing_with_a_settled_exemption_asks_whether_it_decides_admission() -> (
    None
):
    """An admission point (3(a)) asks its own listing question, not the generic use one."""
    listing = annex_iii("annex:III:3:a", YES, open_question=OPEN, on="uses")
    result = outcome(answer(listing, EXEMPT_C))
    assert result.annex_iii_exempt
    assert result.high_risk_route is None
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "decides_admission"


@pytest.mark.parametrize(
    "given",
    [
        pytest.param(
            answer(LISTING_OPEN, art_6_3(Art63Condition.C, open_question=OPEN)),
            id="exemption-open",
        ),
        pytest.param(answer(LISTING_OPEN, art_6_3()), id="no-condition"),
        pytest.param(
            answer(LISTING_OPEN, art_6_3(Art63Condition.C, profiling=YES)), id="profiling-yes"
        ),
        pytest.param(
            answer(LISTING_OPEN, art_6_3(Art63Condition.C, profiling=Answer.UNKNOWN)),
            id="profiling-unknown",
        ),
        pytest.param(
            answer(annex_iii("annex:III:4:b", YES, open_question=OPEN), EXEMPT_C),
            id="listing-open-unnamed",
        ),
        pytest.param(
            answer(
                LISTING_OPEN,
                EXEMPT_C,
                annex_i("annex:I:A:11", YES, YES, YES, open_question=OPEN, on="covered"),
            ),
            id="annex-i-open",
        ),
    ],
)
def test_an_open_listing_stays_open_unless_the_exemption_is_settled(given: HighRiskAnswer) -> None:
    """Never moot when the exemption is open or not met, profiling is "yes" or unknown, the open
    question names no listing fact, or an Annex I route is open: the step stays ambiguous with
    high-risk assumed, as before."""
    result = outcome(given)
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    assert result.high_risk_route is not None
    assert not result.annex_iii_exempt


@pytest.mark.parametrize(
    ("given", "route"),
    [
        pytest.param(
            answer(annex_iii("annex:III:4:b", Answer.NO, open_question=OPEN), EXEMPT_C),
            None,
            id="ruled-out",
        ),
        pytest.param(
            answer(LISTING_OPEN, EXEMPT_C, MEDICAL_DEVICE),
            HighRiskRoute.ANNEX_I,
            id="annex-i-high-risk",
        ),
    ],
)
def test_a_point_decided_otherwise_is_not_made_exempt(
    given: HighRiskAnswer, route: HighRiskRoute | None
) -> None:
    """A point ruled out (its gate "no", nothing named open) is decided not high-risk and not
    exempt; a decided Annex I route still wins."""
    result = outcome(given)
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is route
    assert not result.annex_iii_exempt


@pytest.mark.parametrize(
    ("point", "uses", "user", "is_open"),
    [
        pytest.param("annex:III:4:a", Answer.NO, Answer.NO, False, id="use-no"),
        pytest.param("annex:III:5:a", YES, Answer.NO, True, id="5a-user-no"),
    ],
)
def test_an_annex_iii_question_that_names_no_fact_stays_open_once_raised(
    point: str, uses: Answer, user: Answer, is_open: bool
) -> None:
    """R1, the Annex III twin: `uses` is the point's gate, so 4(a) answered "no" and not held
    open is not raised (not high-risk), whatever `settled_in_law` says. 5(a) with its use met
    is raised, and left unsettled without a name it stays open."""
    result = outcome(answer(annex_iii(point, uses, user, open_question=OPEN)))
    if is_open:
        assert_ambiguous(result, HighRiskRoute.ANNEX_III)
        return
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is None
    assert result.annex_point is None
    assert result.step.open_question is None


@pytest.mark.parametrize(
    ("uses", "user"),
    [
        pytest.param(Answer.NO, Answer.NO, id="use-no"),
        pytest.param(YES, Answer.NO, id="use-yes"),
        pytest.param(Answer.UNKNOWN, Answer.NO, id="use-unknown"),
    ],
)
def test_an_open_on_naming_a_fact_the_point_does_not_read_reads_as_none(
    uses: Answer, user: Answer
) -> None:
    """R2: 4(a) names no user, so `public_authority` is no fact of it; a question named on it
    reads as unnamed (it is not held strict), and R1 applies as for "none"."""
    misnamed = outcome(
        answer(annex_iii("annex:III:4:a", uses, user, open_question=OPEN, on="public_authority"))
    )
    unnamed = outcome(answer(annex_iii("annex:III:4:a", uses, user, open_question=OPEN)))
    assert misnamed == unnamed
    held = node.held_strict_answer(
        answer(annex_iii("annex:III:4:a", uses, user, open_question=OPEN, on="public_authority"))
    )
    assert held.annex_iii.public_authority is Answer.NO
    assert node.annex_iii_facts("annex:III:4:a") == {"uses"}
    assert node.annex_iii_facts("annex:III:5:a") == {"uses", "public_authority"}
    assert node.annex_iii_facts(None) == frozenset()


def test_an_open_art_6_3_exemption_is_ambiguous_with_high_risk_assumed() -> None:
    art63 = art_6_3(Art63Condition.D, Answer.NO, open_question=OPEN)
    result = outcome(answer(RANKS_APPLICANTS, art63))
    assert_ambiguous(result, HighRiskRoute.ANNEX_III)
    assert not result.annex_iii_exempt


def test_an_open_art_6_3_answer_outside_annex_iii_changes_nothing() -> None:
    result = outcome(answer(art63=art_6_3(open_question=OPEN)))
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is None


def test_a_settled_route_is_read_as_before() -> None:
    settled = outcome(answer(one=annex_i("annex:I:A:11", YES, YES, Answer.NO)))
    assert settled.step.status is Status.DECIDED
    assert settled.high_risk_route is None


def test_a_decided_route_beats_an_open_question_on_the_other_route() -> None:
    open_i = annex_i("annex:I:A:11", YES, YES, YES, open_question=OPEN)
    result = outcome(answer(RANKS_APPLICANTS, one=open_i))
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    open_iii = annex_iii("annex:III:4:a", YES, open_question=OPEN)
    result = outcome(answer(open_iii, one=MEDICAL_DEVICE))
    assert result.step.status is Status.DECIDED
    assert result.high_risk_route is HighRiskRoute.ANNEX_I


def test_an_unsettled_route_without_its_question_gets_the_fixed_one() -> None:
    one = AnnexIAnswer.model_validate(
        {**annex_i("annex:I:A:11", YES, YES, YES).model_dump(), "settled_in_law": "no"}
    )
    result = outcome(answer(one=one), language=Language.DE)
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    open_question = result.step.open_question
    assert open_question is not None
    assert open_question.question == node.OPEN_FALLBACK[Language.DE]["annex_i"][0]
    assert open_question.readings[0].explanation.startswith("Hochrisiko")


def test_no_route_is_a_decided_not_high_risk() -> None:
    result = outcome(answer())
    assert result.high_risk_route is None
    assert result.annex_point is None
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:6:1", "art:6:2"]
    assert result.follow_up_questions == ()


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param(answer(), ["art:6:1", "art:6:2"], id="no-match"),
        pytest.param(
            answer(RANKS_APPLICANTS, art_6_3(Art63Condition.D, profiling=YES)),
            ["annex:III:4:a", "art:6:2", "art:6:3"],
            id="match",
        ),
    ],
)
def test_the_step_cites_the_paragraphs_it_checked_not_art_6(
    given: HighRiskAnswer, expected: list[str]
) -> None:
    """E16, both ways: the two routes it ruled out, or the Annex III point with Art. 6(2) and the
    Art. 6(3) paragraph whose last subparagraph (profiling, not split out in the corpus) keeps it
    high-risk; never Art. 6 as a whole."""
    assert cited(outcome(given)) == expected


def test_german_decisions_and_questions() -> None:
    result = outcome(
        answer(one=annex_i("annex:I:A:11", YES, YES, Answer.UNKNOWN)), language=Language.DE
    )
    missing = result.step.missing_fact
    assert missing is not None
    assert "Verordnung (EU) 2017/745 über Medizinprodukte" in missing.text
    assert "Konformitätsbewertung durch Dritte" in missing.text
    assert "Anhang I" in result.step.decision
    assert all(c.language is Language.DE for c in result.step.citations)


def test_the_law_title_is_shortened_to_number_and_subject() -> None:
    assert law_title(provision("annex:I:A:6", ANNEX_I_TEXT["annex:I:A:6"])) == (
        "Directive 2014/53/EU on radio equipment"
    )
    de = provision("annex:I:A:11", DE_ANNEX_I_TEXT["annex:I:A:11"], Language.DE)
    assert law_title(de) == "Verordnung (EU) 2017/745 über Medizinprodukte"
    pressure = provision(
        "annex:I:A:7",
        "7. Richtlinie 2014/68/EU des Europäischen Parlaments und des Rates vom 15. Mai 2014 zur "
        "Harmonisierung der Rechtsvorschriften der Mitgliedstaaten über die Bereitstellung von "
        "Druckgeräten auf dem Markt (ABl. L 189);",
        Language.DE,
    )
    assert law_title(pressure) == "Richtlinie 2014/68/EU über Druckgeräte"
    machinery = provision(
        "annex:I:A:1",
        "1. Richtlinie 2006/42/EG des Europäischen Parlaments und des Rates vom 17. Mai 2006 über "
        "Maschinen und zur Änderung der Richtlinie 95/16/EG (ABl. L 157 vom 9.6.2006, S. 24)",
        Language.DE,
        LawVersion.ORIGINAL,
    )
    assert law_title(machinery) == "Richtlinie 2006/42/EG über Maschinen"


# --- The original text (E11) --------------------------------------------------------------------

ORIGINAL = LawVersion.ORIGINAL
OMNIBUS_PARAGRAPHS = ("6(1a)", "6(1b)", "6(1c)", "Abs. 1a", "Abs. 1b", "Abs. 1c")
"""How a decision would name Art. 6(1a)-(1c), which only the Omnibus added."""


def test_machinery_is_annex_i_a_1_under_the_original_text_and_b_21_under_the_amended() -> None:
    """The Omnibus moved machinery to Section B: under the original text a decided machinery
    guard is an ordinary Section A product, so Art. 2(2) doesn't take its AI Act duties away."""
    original_ids = [p.provision_id for p in retrieved(law_version=ORIGINAL).annex_i]
    amended_ids = [p.provision_id for p in retrieved().annex_i]
    assert ("annex:I:A:1" in original_ids, "annex:I:B:21" in original_ids) == (True, False)
    assert ("annex:I:A:1" in amended_ids, "annex:I:B:21" in amended_ids) == (False, True)
    result = outcome(answer(one=annex_i("annex:I:A:1", YES, YES, YES)), law_version=ORIGINAL)
    assert result.high_risk_route is HighRiskRoute.ANNEX_I
    assert result.annex_point == "annex:I:A:1"
    assert result.step.status is Status.DECIDED
    assert "Directive 2006/42/EC on machinery" in result.step.decision
    assert "Art. 2(2)" not in result.step.decision
    assert "art:2:2" not in cited(result)
    assert {c.law_version for c in result.step.citations} == {ORIGINAL}


def test_a_section_b_product_cites_the_original_art_2_2_under_the_original_text() -> None:
    """E8's follow-up: the original Art. 2(2) keeps Art. 6(1), 102 to 109 and 112; Art. 60a
    and Art. 110 and 111 come only with the Omnibus."""
    result = outcome(answer(one=annex_i("annex:I:B:19", YES, YES, YES)), law_version=ORIGINAL)
    decision = result.step.decision
    assert "only Art. 6(1), Art. 102 to 109 and Art. 112 of the AI Act apply" in decision
    assert "60a" not in decision
    assert "art:2:2" in cited(result)
    german = TEXTS[Language.DE]["i_section_b"].format(
        law="", **version_words(Language.DE, ORIGINAL)
    )
    assert "nur Art. 6 Abs. 1, Art. 102 bis 109 und Art. 112" in german
    amended = outcome(answer(one=annex_i("annex:I:B:21", YES, YES, YES))).step.decision
    assert "only Art. 6(1), Art. 60a and Art. 102 to 112 of the AI Act apply" in amended
    machinery = "Verordnung (EU) 2023/1230 über Maschinen"
    german_amended = TEXTS[Language.DE]["i_section_b"].format(
        law=machinery, **version_words(Language.DE, LawVersion.AMENDED)
    )
    assert german_amended == (
        "Verordnung (EU) 2023/1230 über Maschinen ist in Anhang I Abschnitt B aufgeführt, daher "
        "gelten nach Art. 2 Abs. 2 von der KI-Verordnung nur Art. 6 Abs. 1, Art. 60a und "
        "Art. 102 bis 112: Die Hochrisiko-Anforderungen erreichen das Produkt über "
        "Verordnung (EU) 2023/1230 über Maschinen, die KI-Verordnung selbst legt keine weiteren "
        "Pflichten auf."
    )


@pytest.mark.parametrize(
    ("facts", "language", "sentence"),
    [
        pytest.param(
            (YES, Answer.NO, YES),
            Language.EN,
            "The AI system is not a safety component of the product covered by Regulation (EU) "
            "2017/745 on medical devices (Annex I Section A point 11) (Art. 6(1)(a), 6(1a)), so "
            "Art. 6(1) does not apply.",
            id="en-not-a-safety-component",
        ),
        pytest.param(
            (YES, YES, Answer.NO),
            Language.EN,
            "The product covered by Regulation (EU) 2017/745 on medical devices (Annex I Section "
            "A point 11) does not need a third-party conformity assessment for health and safety "
            "(Art. 6(1)(b), 6(1c)), so Art. 6(1) does not apply.",
            id="en-no-third-party-assessment",
        ),
        pytest.param(
            (YES, Answer.NO, YES),
            Language.DE,
            "Das KI-System ist kein Sicherheitsbauteil des Produkts, das unter Verordnung (EU) "
            "2017/745 über Medizinprodukte fällt (Anhang I Abschnitt A Nummer 11) (Art. 6 Abs. 1 "
            "Buchst. a, Abs. 1a), daher gilt Art. 6 Abs. 1 nicht.",
            id="de-not-a-safety-component",
        ),
        pytest.param(
            (YES, YES, Answer.NO),
            Language.DE,
            "Das Produkt, das unter Verordnung (EU) 2017/745 über Medizinprodukte fällt (Anhang I "
            "Abschnitt A Nummer 11), muss keine Konformitätsbewertung durch Dritte zu Gesundheit "
            "und Sicherheit durchlaufen (Art. 6 Abs. 1 Buchst. b, Abs. 1c), daher gilt Art. 6 "
            "Abs. 1 nicht.",
            id="de-no-third-party-assessment",
        ),
    ],
)
def test_the_amended_text_cites_art_6_1a_and_1c_in_the_exact_sentence(
    facts: tuple[Answer, Answer, Answer], language: Language, sentence: str
) -> None:
    """The re-audit's gap: the amended punctuation of Art. 6(1a)/(1c) pinned to the character."""
    result = outcome(answer(one=annex_i("annex:I:A:11", *facts)), language)
    assert result.high_risk_route is None
    assert result.step.decision == f"{TEXTS[language]['none']} {sentence}"


@pytest.mark.parametrize(
    ("facts", "amended_names"),
    [
        pytest.param((YES, Answer.NO, YES), "6(1a)", id="not-a-safety-component"),
        pytest.param((YES, YES, Answer.NO), "6(1c)", id="no-third-party-assessment"),
    ],
)
def test_the_original_text_names_no_art_6_1a_to_1c(
    facts: tuple[Answer, Answer, Answer], amended_names: str
) -> None:
    given = answer(one=annex_i("annex:I:A:11", *facts))
    amended = outcome(given).step.decision
    assert amended_names in amended
    for language in Language:
        original = outcome(given, language, ORIGINAL)
        assert original.high_risk_route is None
        assert not any(name in original.step.decision for name in OMNIBUS_PARAGRAPHS)
    english = outcome(given, law_version=ORIGINAL).step.decision
    assert "(Art. 6(1)(a))" in english or "(Art. 6(1)(b))" in english
    assert "for health and safety" not in english


@pytest.mark.parametrize(
    ("language", "restriction"),
    [(Language.EN, "for health and safety"), (Language.DE, "zu Gesundheit und Sicherheit")],
)
def test_the_third_party_question_asks_art_6_1c_only_under_the_amended_text(
    language: Language, restriction: str
) -> None:
    """Under the original text any third-party assessment counts (no Art. 6(1c)): the question
    must not let a radio-only notified body be answered "no"."""
    given = answer(one=annex_i("annex:I:A:11", YES, YES, Answer.UNKNOWN))
    asked: dict[LawVersion, str] = {}
    for law_version in LawVersion:
        result = outcome(given, language, law_version)
        missing = result.step.missing_fact
        assert missing is not None and missing.id == "third_party_assessment"
        assert missing.text in result.step.decision
        asked[law_version] = missing.text
    assert restriction in asked[LawVersion.AMENDED]
    assert restriction not in asked[ORIGINAL]
    assert asked[ORIGINAL] == asked[LawVersion.AMENDED].replace(f" {restriction}", "")
    assert not any(name in asked[ORIGINAL] for name in OMNIBUS_PARAGRAPHS)


def test_only_the_original_text_gets_the_note_that_art_6_1a_to_1c_do_not_exist() -> None:
    """The amended request stays byte for byte as recorded; the original one opens with the
    note, after the cached instructions."""
    amended = node.high_risk_messages(state(), retrieved())
    original = node.high_risk_messages(state(law_version=ORIGINAL), retrieved(law_version=ORIGINAL))
    assert original[0].content == amended[0].content == node.HIGH_RISK_INSTRUCTIONS
    assert str(amended[1].content).startswith("Annex I:\n")
    assert str(original[1].content).startswith(
        f"Law version:\n{node.ORIGINAL_INSTRUCTIONS}\nAnnex I:\n"
    )
    assert "It has no Art. 6(1a), (1b) or (1c)" in " ".join(node.ORIGINAL_INSTRUCTIONS.split())


@pytest.mark.parametrize(
    ("language", "text", "line"),
    [
        pytest.param(
            Language.EN,
            ORIGINAL_ANNEX_I_TEXT["annex:I:A:1"],
            "[annex:I:A:1] Directive 2006/42/EC on machinery (repealed by Regulation (EU) "
            "2023/1230 on machinery with effect from 20 January 2027; references to the Directive "
            "are read as references to that Regulation)",
            id="en",
        ),
        pytest.param(
            Language.DE,
            "1. Richtlinie 2006/42/EG des Europäischen Parlaments und des Rates vom 17. Mai 2006 "
            "über Maschinen und zur Änderung der Richtlinie 95/16/EG (ABl. L 157 vom 9.6.2006, "
            "S. 24)",
            "[annex:I:A:1] Richtlinie 2006/42/EG über Maschinen (mit Wirkung vom 20. Januar 2027 "
            "aufgehoben durch die Verordnung (EU) 2023/1230 über Maschinen; Verweise auf die "
            "Richtlinie gelten als Verweise auf diese Verordnung)",
            id="de",
        ),
    ],
)
def test_the_original_a_1_entry_names_the_machinery_regulation_that_repeals_it(
    language: Language, text: str, line: str
) -> None:
    """The original A.1 names only Directive 2006/42/EC: the prompt adds Regulation (EU)
    2023/1230, which repeals it, so a product under the Regulation is matched to A.1."""
    assert annex_i_entry(provision("annex:I:A:1", text, language, ORIGINAL)) == line
    assert annex_i_entry(provision("annex:I:A:1", text, language)) == line.split(" (")[0]


def test_only_the_original_prompt_lists_machinery_with_its_repealing_regulation() -> None:
    entry = (
        "[annex:I:A:1] Directive 2006/42/EC on machinery (repealed by Regulation (EU) "
        "2023/1230 on machinery with effect from 20 January 2027; references to the Directive are "
        "read as references to that Regulation)\n"
    )
    original = node.high_risk_messages(state(law_version=ORIGINAL), retrieved(law_version=ORIGINAL))
    amended = node.high_risk_messages(state(), retrieved())
    assert entry in str(original[1].content)
    assert "repealed by" not in str(amended[1].content)


# --- Retrieval and analogy -----------------------------------------------------------------------


def test_every_search_passes_the_exclude_filter_through() -> None:
    """The DoD's pass-through test: in LOO mode the case's exclusions reach every search."""
    search = FakeSearch(guidance={Language.EN: GUIDE_HITS})
    library = FakeLibrary(search)
    check = HighRiskCheck(_settings(), chat=_fake_chat(answer(RANKS_APPLICANTS)), library=library)
    check(state(language=Language.DE, exclude=EXCLUDED))
    assert len(search.calls) == 2  # guidance in German, then in English
    for call in search.calls:
        assert call["exclude_source_example_ids"] == EXCLUDED


class FakeEmbedder:
    model = "fake"
    dimensions = 3

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0, 1.0]


def test_the_corpus_hands_the_filter_to_search_ai_act_over_one_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every search carries the exclusions and no cut-off, over the step's one connection and
    embedder, and never asks for held-out examples."""
    seen: list[dict[str, object]] = []

    def spy(
        query: str, language: Language, law_version: LawVersion, as_of: date, **kwargs: object
    ) -> SearchResults:
        seen.append(kwargs)
        return FakeSearch()(query, language, law_version, as_of, **kwargs)

    monkeypatch.setattr(corpus_module, "search_ai_act", spy)
    connection, embedder = cast(psycopg.Connection, object()), FakeEmbedder()
    library = HighRiskCorpus(connection, embedder)
    retrieve(state(language=Language.DE, exclude=EXCLUDED), _only_search(library))
    assert len(seen) == 2
    for kwargs in seen:
        assert kwargs["exclude_source_example_ids"] == EXCLUDED
        assert kwargs["max_distance"] is None
        assert kwargs["connection"] is connection
        assert kwargs["embedder"] is embedder
        assert kwargs["include_held_out"] is False  # held-out examples stay hidden


def _only_search(library: HighRiskCorpus) -> HighRiskLibrary:
    """`library`'s searches with `fake_lookup`'s texts, so no database is needed."""

    class Searching(FakeLibrary):
        def search(
            self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
        ) -> tuple[SearchHit, ...]:
            return library.search(query, lookup, language=language, doc_type=doc_type, limit=limit)

    return Searching()


def test_provision_lookups_use_the_steps_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    def spy(
        provision_id: str, *args: object, connection: object, include_held_out: bool
    ) -> Provision:
        seen.append(connection)
        return provision(provision_id)

    monkeypatch.setattr(corpus_module, "get_provision", spy)
    connection = cast(psycopg.Connection, object())
    library = HighRiskCorpus(connection, FakeEmbedder())
    library.provision("art:6:1", Lookup(Language.EN, LawVersion.AMENDED, AS_OF, ()))
    assert seen == [connection]


class FakeConnection:
    """Open from `connect()` until its `with` block ends."""

    def __init__(self) -> None:
        self.is_open = True

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        self.is_open = False


class ProbeChat(GenericFakeChatModel):
    """A fake chat that runs `probe` when the model is called."""

    probe: Callable[[], None]

    def invoke(self, input: object, config: object = None, **kwargs: object) -> AIMessage:  # type: ignore[override]
        self.probe()
        return super().invoke(input, config, **kwargs)  # type: ignore[arg-type]


def test_a_check_without_a_library_builds_one_embedder_and_holds_no_connection_over_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production path: the embedder is built once from the check's own settings and used
    by every search; each step reads over a short connection before the model call and another
    for its citations after it, and none is open while the model answers."""
    connections: list[FakeConnection] = []
    embedders: list[tuple[object, Settings | None]] = []
    searched_with: list[object] = []

    def fake_connect() -> FakeConnection:
        connections.append(FakeConnection())
        return connections[-1]

    class Embeddings(FakeEmbedder):
        def __init__(self, settings: Settings | None = None) -> None:
            embedders.append((self, settings))

    def search(
        query: str, language: Language, law_version: LawVersion, as_of: date, **kwargs: object
    ) -> SearchResults:
        connection = kwargs.pop("connection")
        assert isinstance(connection, FakeConnection) and connection.is_open
        searched_with.append(kwargs.pop("embedder"))
        return FakeSearch()(query, language, law_version, as_of, **kwargs)

    def lookup(
        provision_id: str,
        *args: object,
        connection: FakeConnection,
        include_held_out: bool,
    ) -> Provision:
        assert not include_held_out
        assert connection.is_open
        return fake_lookup(provision_id, *args)  # type: ignore[arg-type]

    def no_connection_open() -> None:
        assert not any(c.is_open for c in connections)

    monkeypatch.setattr(corpus_module, "connect", fake_connect)
    monkeypatch.setattr(corpus_module, "OpenRouterEmbeddings", Embeddings)
    monkeypatch.setattr(corpus_module, "search_ai_act", search)
    monkeypatch.setattr(corpus_module, "get_provision", lookup)
    replies = iter([AIMessage(content=answer(RANKS_APPLICANTS).model_dump_json())] * 2)
    settings = _settings()
    check = HighRiskCheck(settings, chat=ProbeChat(messages=replies, probe=no_connection_open))
    check(state())
    check(state())
    [(embedder, built_from)] = embedders
    assert built_from is settings
    assert searched_with and all(used is embedder for used in searched_with)
    assert len(connections) == 4  # two per step: retrieval, then citations
    no_connection_open()


def test_german_guidance_falls_back_to_english_and_is_marked_english_only() -> None:
    search = FakeSearch(guidance={Language.EN: GUIDE_HITS})
    found = retrieve(state(language=Language.DE), FakeLibrary(search))
    assert [call["language"] for call in search.calls] == [Language.DE, Language.EN]
    assert found.guidance == GUIDE_HITS
    result = to_outcome(
        answer(annex_iii("annex:III:4:a", YES, examples=(EXAMPLE,))),
        state(language=Language.DE),
        found,
        FakeLibrary(),
    )
    guidance = [c for c in result.step.citations if c.provision_id == EXAMPLE]
    assert len(guidance) == 1
    assert guidance[0].english_only
    assert guidance[0].document_status is DocumentStatus.DRAFT


def test_german_guidance_found_in_german_is_not_searched_again() -> None:
    german = (hit("guide:guide-definition:para:001", Language.DE),)
    search = FakeSearch(guidance={Language.DE: german})
    assert retrieve(state(language=Language.DE), FakeLibrary(search)).guidance == german
    assert len(search.calls) == 1


def _prompt_block(human: object, heading: str) -> list[str]:
    assert isinstance(human, str)
    return human.split(f"{heading}:\n", 1)[1].split("\n\n", 1)[0].splitlines()


def _prompt_annex_iii_ids(language: Language) -> list[str]:
    human = node.high_risk_messages(state(language=language), retrieved(language))[1].content
    return [line.split("]", 1)[0].removeprefix("[") for line in _prompt_block(human, "Annex III")]


@pytest.mark.parametrize("language", [Language.EN, Language.DE])
def test_the_prompt_lists_every_annex_iii_leaf_once_with_its_text(language: Language) -> None:
    """All 25 leaves, looked up in the case's language, whatever the description; one line
    each with its id and its text on that line (user, 2026-09-30)."""
    human = node.high_risk_messages(state(language=language), retrieved(language))[1].content
    lines = _prompt_block(human, "Annex III")
    assert lines == [f"[{point}] Text of {point}." for point in ANNEX_III_POINTS]
    assert len(ANNEX_III_POINTS) == 25
    assert all(p.language is language for p in retrieved(language).annex_iii)


def test_a_leaf_text_spread_over_lines_is_shown_on_one() -> None:
    lookup_text = "(a) AI systems intended\n  to be used for recruitment;"
    found = Retrieved(annex_i=(), annex_iii=(provision("annex:III:4:a", lookup_text),), guidance=())
    human = node.high_risk_messages(state(), found)[1].content
    assert _prompt_block(human, "Annex III") == [
        "[annex:III:4:a] (a) AI systems intended to be used for recruitment;"
    ]


@pytest.mark.parametrize("language", [Language.EN, Language.DE])
def test_the_annex_iii_point_enum_is_the_prompts_ids(language: Language) -> None:
    sent = node.high_risk_response_format(
        _prompt_annex_iii_ids(language), _prompt_annex_i_ids(language)
    )
    point = _point_schema(sent, "AnnexIIIAnswer")
    leaves = {"type": "string", "enum": _prompt_annex_iii_ids(language)}
    assert point == {"anyOf": [leaves, {"type": "null"}], "title": "Point"}


class LibraryWithoutLeaf(FakeLibrary):
    """A text without Annex III 8(b), as an older or partial corpus might have."""

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        if provision_id == "annex:III:8:b":
            raise ProvisionNotFoundError(provision_id)
        return super().provision(provision_id, lookup)


def test_a_leaf_the_text_lacks_is_neither_shown_nor_allowed() -> None:
    content = answer(RANKS_APPLICANTS).model_dump_json()
    chat = RecordingChat(messages=iter([AIMessage(content=content)]))
    library = LibraryWithoutLeaf()
    HighRiskCheck(_settings(), chat=chat, library=library)(state())
    human = node.high_risk_messages(state(), retrieve(state(), library))[1].content
    shown = [line.split("]", 1)[0].removeprefix("[") for line in _prompt_block(human, "Annex III")]
    [sent] = chat.formats
    point = _point_schema(sent, "AnnexIIIAnswer")
    assert isinstance(point, dict)
    assert len(shown) == 24
    assert "annex:III:8:b" not in shown
    assert point["anyOf"][0]["enum"] == shown


def test_the_chosen_annex_iii_point_is_cited_from_the_lookup_already_made() -> None:
    fetched: list[str] = []

    class Counting(FakeLibrary):
        def provision(self, provision_id: str, lookup: Lookup) -> Provision:
            fetched.append(provision_id)
            return super().provision(provision_id, lookup)

    content = answer(RANKS_APPLICANTS).model_dump_json()
    chat = _fake_chat(content)
    result = HighRiskCheck(_settings(), chat=chat, library=Counting())(state())
    assert "annex:III:4:a" in cited(result)
    assert fetched.count("annex:III:4:a") == 1  # the Annex III lookup, not again for the citation


def test_annex_i_is_shown_one_line_per_existing_point_with_its_id() -> None:
    """Only ids the text has reach the model: `annex:I:A:1` (machinery before the Omnibus) is
    looked up but has no text in the fake amended Act, so it isn't listed."""
    human = node.high_risk_messages(state(), retrieved())[1].content
    assert isinstance(human, str)
    listed = human.split("Annex I:\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert listed == [
        "[annex:I:A:6] Directive 2014/53/EU on radio equipment",
        "[annex:I:A:11] Regulation (EU) 2017/745 on medical devices",
        "[annex:I:B:21] Regulation (EU) 2023/1230 on machinery",
    ]


def test_the_original_text_is_searched_without_a_date() -> None:
    search = FakeSearch()
    retrieve(state(law_version=LawVersion.ORIGINAL), FakeLibrary(search))
    assert all(call["law_version"] is LawVersion.ORIGINAL for call in search.calls)


def test_only_retrieved_examples_are_cited_as_analogies() -> None:
    examples = (EXAMPLE, "guide:guide-high-risk-annex-iii:ex:999", "annex:III:4:a")
    result = outcome(answer(annex_iii("annex:III:4:a", YES, examples=examples)))
    assert EXAMPLE in cited(result)
    assert "guide:guide-high-risk-annex-iii:ex:999" not in cited(result)
    assert f"Compared with the guideline examples {EXAMPLE}." in result.step.decision


# --- The model call ------------------------------------------------------------------------------


def _settings(**values: object) -> Settings:
    pinned = {"engine_model": LUNA, "engine_provider": LUNA_PROVIDER, **values}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **REFUSAL_ROUTE, **pinned)  # pyright: ignore[reportCallIssue]


def _fake_chat(given: HighRiskAnswer | str) -> GenericFakeChatModel:
    content = given if isinstance(given, str) else given.model_dump_json()
    return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))


def test_the_prompt_puts_instructions_first_retrieval_next_and_the_description_last() -> None:
    messages = node.high_risk_messages(state(), retrieved())
    assert messages[0].content == node.HIGH_RISK_INSTRUCTIONS
    human = messages[1].content
    assert isinstance(human, str)
    assert human.index("Annex I:") < human.index("Annex III:")
    assert human.index("Text of annex:III:4:a.") < human.index("Description:")
    assert human.endswith(WORKED_EXAMPLE)
    assert "art:26:1" not in human


def test_the_check_runs_in_the_graph_and_sets_its_findings() -> None:
    check = HighRiskCheck(
        _settings(),
        chat=_fake_chat(answer(one=MEDICAL_DEVICE)),
        library=FakeLibrary(),
    )
    scripted = scripted_nodes(Script(risk_class=RiskClass.HIGH_RISK))
    checks = {**scripted.checks, StepName.HIGH_RISK: check}
    graph = build_graph(
        EngineNodes(facts=scripted.facts, checks=checks, finalize=scripted.finalize)
    )
    final = graph.invoke(
        {
            "description": PUMP_TOOL,
            "language": Language.EN,
            "law_version": LawVersion.AMENDED,
            "as_of": AS_OF,
            "exclude_source_example_ids": (),
        }
    )
    assert final["high_risk_route"] is HighRiskRoute.ANNEX_I
    assert final["annex_point"] == "annex:I:A:11"
    assert [s.step for s in final["steps"]][2] is StepName.HIGH_RISK


def test_a_reply_that_does_not_fit_the_schema_is_a_broken_output() -> None:
    reply = '{"annex_iii": {"point": "SECRET-VALUE-7731"}}'
    check = HighRiskCheck(_settings(), chat=_fake_chat(reply), library=FakeLibrary())
    with pytest.raises(HighRiskOutputError, match="doesn't fit the schema") as raised:
        check(state())
    assert "SECRET-VALUE-7731" not in str(raised.value)


REFUSAL_TEXT = "I'm sorry, but I cannot assist with that request."


def _filtered_check(content: str = REFUSAL_TEXT) -> HighRiskCheck:
    """The node over a reply the provider's content filter stopped (decision 029)."""
    reply = AIMessage(content=content, response_metadata={"finish_reason": "content_filter"})
    chat = GenericFakeChatModel(messages=iter([reply]))
    return HighRiskCheck(_settings(), chat=chat, library=FakeLibrary())


def test_a_provider_refusal_finds_nothing_for_a_person_to_review() -> None:
    """Decision 030: no route, Annex point or exemption is assumed, so no class rests on it."""
    result = _filtered_check()(state())
    step = result.step
    assert result.high_risk_route is None
    assert (result.annex_point, result.annex_iii_exempt) == (None, False)
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.error == "provider_refusal"
    assert step.missing_fact is not None
    assert step.missing_fact.id == "high_risk_person_review"
    assert result.follow_up_questions == (step.missing_fact,)
    assert cited(result) == ["art:6:1", "art:6:2"]
    assert step.decision == NOT_ASSESSED["en"]


def test_a_high_risk_refusal_is_reported_in_german() -> None:
    result = _filtered_check()(state(language=Language.DE))
    assert result.step.decision == NOT_ASSESSED["de"]
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.text.startswith("Bitte lassen Sie")


def test_a_filtered_high_risk_reply_with_a_usable_answer_is_used() -> None:
    result = _filtered_check(answer(RANKS_APPLICANTS).model_dump_json())(state())
    assert (result.step.error, result.annex_point) == (None, "annex:III:4:a")


def test_the_output_cap_leaves_room_for_reasoning() -> None:
    """own-e-14 (both routes apply) spent all of 3000 output tokens on reasoning; 6000 fits."""
    check = HighRiskCheck(_settings(), library=FakeLibrary())
    assert_pinned_route(check._route, 10000)  # pyright: ignore[reportAttributeAccessIssue]


def test_the_engine_model_must_be_pinned() -> None:
    with pytest.raises(LLMConfigError, match="ENGINE_PROVIDER"):
        HighRiskCheck(_settings(engine_provider=None))


def test_the_response_format_requires_every_field() -> None:
    schema = node.HIGH_RISK_RESPONSE_FORMAT["json_schema"]
    assert isinstance(schema, dict)
    assert schema["schema"]["required"] == ["annex_iii", "art_6_3", "annex_i", "question"]


def test_each_route_answers_its_legal_openness_right_after_its_facts() -> None:
    """Strict structured output fills fields in order, so `settled_in_law` and `open_question`
    sit after each route's facts and before its summary, and on the Annex routes `open_on`
    (E19) right after them."""
    definitions = node.HIGH_RISK_RESPONSE_FORMAT["json_schema"]
    assert isinstance(definitions, dict)
    defs = definitions["schema"]["$defs"]
    openness = ["settled_in_law", "open_question"]
    last_facts = {
        "AnnexIIIAnswer": ("public_authority", [*openness, "open_on", "evidence"]),
        "Art63Answer": ("profiling", [*openness, "evidence"]),
        "AnnexIAnswer": ("third_party_assessment", [*openness, "open_on", "evidence"]),
    }
    for name, (last, after) in last_facts.items():
        fields = defs[name]["required"]
        at = fields.index(last)
        assert fields[at + 1 : at + 1 + len(after)] == after
    named = {name: defs[f"{name}OpenOn"]["enum"] for name in ("AnnexIII", "AnnexI")}
    assert named == {
        "AnnexIII": ["none", "uses", "public_authority"],
        "AnnexI": ["none", "covered", "safety_component_or_product", "third_party_assessment"],
    }
    assert set(node.STRICT_VALUES) == {*named["AnnexIII"][1:], *named["AnnexI"][1:]}
    assert set(node.STRICT_VALUES.values()) == {Answer.YES}


def _prompt_annex_i_ids(language: Language) -> list[str]:
    human = node.high_risk_messages(state(language=language), retrieved(language))[1].content
    assert isinstance(human, str)
    lines = human.split("Annex I:\n", 1)[1].split("\n\n", 1)[0].splitlines()
    return [line.split("]", 1)[0].removeprefix("[") for line in lines]


def _point_schema(response_format: dict[str, object], definition: str) -> object:
    spec = response_format["json_schema"]
    assert isinstance(spec, dict)
    return spec["schema"]["$defs"][definition]["properties"]["point"]


def _annex_i_point_schema(response_format: dict[str, object]) -> object:
    return _point_schema(response_format, "AnnexIAnswer")


class RecordingChat(GenericFakeChatModel):
    """A fake chat that keeps the `response_format` of each call."""

    formats: list[dict[str, object]] = Field(default_factory=list)

    def invoke(self, input: object, config: object = None, **kwargs: object) -> AIMessage:  # type: ignore[override]
        response_format = kwargs["response_format"]
        assert isinstance(response_format, dict)
        self.formats.append(response_format)
        return super().invoke(input, config, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("language", [Language.EN, Language.DE])
def test_the_annex_i_point_enum_is_the_prompts_ids(language: Language) -> None:
    """The ids differ by text (the fake German one has only A.11), so the enum is built per call;
    the shared format keeps its free string."""
    ids = _prompt_annex_i_ids(language)
    assert ids == list(DE_ANNEX_I_TEXT if language is Language.DE else ANNEX_I_TEXT)
    limited = node.high_risk_response_format(ANNEX_III_POINTS, ids)
    assert _annex_i_point_schema(limited) == {
        "anyOf": [{"type": "string", "enum": ids}, {"type": "null"}],
        "title": "Point",
    }
    free = {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Point"}
    assert _annex_i_point_schema(node.HIGH_RISK_RESPONSE_FORMAT) == free
    assert _point_schema(node.HIGH_RISK_RESPONSE_FORMAT, "AnnexIIIAnswer") == free


def test_the_enum_leaves_out_an_annex_i_id_the_prompt_does_not_show() -> None:
    """own-e-07's first recording named `annex:I:A:21`, which no text has."""
    ids = _prompt_annex_i_ids(Language.EN)
    point = _annex_i_point_schema(node.high_risk_response_format(ANNEX_III_POINTS, ids))
    assert isinstance(point, dict)
    assert "annex:I:A:21" not in point["anyOf"][0]["enum"]


def test_no_annex_i_text_leaves_only_null() -> None:
    assert _annex_i_point_schema(node.high_risk_response_format(ANNEX_III_POINTS, [])) == {
        "anyOf": [{"type": "null"}],
        "title": "Point",
    }


def test_the_check_sends_the_limited_schema() -> None:
    content = answer(RANKS_APPLICANTS).model_dump_json()
    chat = RecordingChat(messages=iter([AIMessage(content=content)]))
    HighRiskCheck(_settings(), chat=chat, library=FakeLibrary())(state())
    [sent] = chat.formats
    expected = (_prompt_annex_iii_ids(Language.EN), _prompt_annex_i_ids(Language.EN))
    assert sent == node.high_risk_response_format(*expected)


# --- Replays: INIT's worked example and the Annex I own cases ------------------------------------
#
# Record (live model and embedding calls, and the local corpus; see the story report for the
# cost) with `RECORD_COMMAND`.

ANNEX_I_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "e"


def _annex_i_cases() -> list[BenchmarkCase]:
    paths = sorted(ANNEX_I_CASES_DIR.rglob("*.yaml")) if ANNEX_I_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


ANNEX_I_CASES = _annex_i_cases()


RECORD_COMMAND = "uv run pytest tests/engine/nodes/test_high_risk.py -k replay --record-mode=once"


class RecordedHighRiskLibrary:
    """A `HighRiskLibrary` over the replay's `CorpusRecording`."""

    def __init__(self, recording: CorpusRecording[HighRiskCorpus]) -> None:
        self._recording = recording

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        return self._recording.provision(
            provision_id, lookup, lambda live: live.provision(provision_id, lookup)
        )

    def search(
        self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
    ) -> tuple[SearchHit, ...]:
        call = {"search": query, **lookup_call(lookup), "language": language}
        call |= {"doc_type": doc_type, "limit": limit}

        def ask(live: HighRiskCorpus) -> tuple[SearchHit, ...]:
            return live.search(query, lookup, language=language, doc_type=doc_type, limit=limit)

        return self._recording.hits(call, ask)


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@contextmanager
def _live_corpus(settings: Settings) -> Iterator[HighRiskCorpus]:
    with connect() as connection:
        yield HighRiskCorpus(connection, OpenRouterEmbeddings(settings=settings))


@contextmanager
def _recorded_check(
    settings: Settings,
    record_mode: str,
    cassette_dir: str,
    cassette_name: str,
    record_command: str,
) -> Iterator[HighRiskCheck]:
    """A `HighRiskCheck` over the recorded model and corpus; skips while nothing is recorded,
    naming `record_command`."""
    with corpus_recording(
        cassette_dir,
        cassette_name,
        record_mode,
        record_command,
        lambda: _live_corpus(settings),
    ) as recording:
        yield HighRiskCheck(settings, library=RecordedHighRiskLibrary(recording))


@pytest.fixture
def replay_check(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[HighRiskCheck]:
    """A `HighRiskCheck` over the recorded model and corpus; skips while nothing is recorded."""
    with _recorded_check(
        luna_settings, record_mode, vcr_cassette_dir, default_cassette_name, RECORD_COMMAND
    ) as check:
        yield check


@pytest.mark.vcr
def test_replay_worked_example(replay_check: HighRiskCheck) -> None:
    """INIT's worked example: recruitment use, and ranking is profiling, so no Art. 6(3)."""
    run_state = replay_state(WORKED_EXAMPLE_CASE, AS_OF)
    result = replay_check(run_state)
    assert not unresolved_citations(result.step, run_state)
    assert not whole_articles(result.step)
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.annex_point == "annex:III:4:a"
    assert not result.annex_iii_exempt
    assert result.step.status is Status.DECIDED
    assert "art:6:3" in cited(result)
    assert high_risk_matches(result, WORKED_EXAMPLE_CASE)


def _asks_for_third_party_assessment(result: CheckOutcome, case: BenchmarkCase) -> bool:
    """High-risk assumed on the case's Annex I point, asking whether a third-party conformity
    assessment is required (Art. 6(1)(b))."""
    missing = result.step.missing_fact
    return (
        result.step.status is Status.NEEDS_MORE_INFORMATION
        and result.high_risk_route is HighRiskRoute.ANNEX_I
        and result.annex_point in case_label(case).annex_point
        and missing is not None
        and missing.id == "third_party_assessment"
        and missing.about == "art:6:1:b"
    )


def _decides_high_risk_on_its_annex_i_point(result: CheckOutcome, case: BenchmarkCase) -> bool:
    """Decided high-risk on the case's Annex I point, with no question open in law."""
    return (
        result.step.status is Status.DECIDED
        and result.high_risk_route is HighRiskRoute.ANNEX_I
        and result.annex_point in case_label(case).annex_point
        and result.step.open_question is None
    )


KNOWN_GAPS: dict[str, KnownGap] = {
    "own-e-09-ropeway-wear-forecast": KnownGap(
        "E20's re-record (2026-10-13): the safety-component question is read as settled (yes), "
        "so the step decides high-risk on annex:I:A:8 where the label leaves it legally "
        "ambiguous; a status-only miss, not a false low risk. Run-to-run variance, not E20's "
        "rule: the third-party assessment reads 'yes' in all eight recordings since E5, E19's "
        "first recording (pre-E20 prompt) settled it the same way, and six of the eight hold it "
        "open; the request differs from E19's variance-check recording only by the exemption "
        "rule (and one retrieved passage's place), and the rule applies to an exemption the "
        "company relies on, which own-e-09 doesn't",
        _decides_high_risk_on_its_annex_i_point,
    ),
    "own-e-10-in-house-nodule-finder": KnownGap(
        "E20's re-record (2026-10-13): the exemption rule's first stage. The description shows "
        "in-house use but not the MDR in-house exemption's other conditions (Art. 5(5)), so the "
        "third-party assessment reads 'unknown' and high-risk is assumed on the Annex I route "
        "(MDR, annex:I:A:11) until it is answered (needs_more_information), where the label "
        "leaves the exemption legally ambiguous; a status-only miss, not a false low risk",
        _asks_for_third_party_assessment,
    ),
}
"""Recorded cases whose high-risk outcome differs from the label, with the reason and the
reading they give instead; each fails when it starts matching, so the entry is removed."""


MEDICAL_DEVICES = "(EU) 2017/745"
"""The Medical Device Regulation, as both languages name it."""
MDR_HIGH_RISK = AnswerOutcome(
    risk_class=RiskClass.HIGH_RISK,
    high_risk_route=HighRiskRoute.ANNEX_I,
    provision_id="annex:I:A:11",
    duties_from=date(2028, 8, 2),
)
"""What a yes to own-e-10's third-party question settles: high-risk under the MDR, its duties
from the Annex I date (E12 DoD)."""
PRODUCT_LAW_QUESTIONS: dict[str, tuple[str, AnswerOutcome | None]] = {
    "own-e-08-heart-rhythm-app": ("intended_purpose", None),  # a second Annex I fact is open
    "own-e-10-in-house-nodule-finder": ("third_party_assessment", MDR_HIGH_RISK),
}
"""Recorded cases whose step asks an Annex I question, and what a yes settles (E12 DoD)."""
AMBIGUOUS_CASES = {
    "own-e-09-ropeway-wear-forecast": "safety_component_or_product",
    "own-e-10-in-house-nodule-finder": "third_party_assessment",
}
"""The Annex I cases labelled legally ambiguous, with the key fact the law leaves open: own-e-09
the safety component, own-e-10 the third-party assessment its in-house exemption leaves open
(E20). A recorded step that matches the label must hold that fact open with E12's two readings
(E12 DoD); a `KNOWN_GAPS` case doesn't match it, so its gap's reading is checked instead, and
the check applies again once the gap is removed."""
ANNEX_I_READING_TITLES = {
    Language.EN: ("High-risk under Art. 6(1)", "Art. 6(1) not met"),
    Language.DE: ("Hochrisiko nach Art. 6 Abs. 1", "Art. 6 Abs. 1 nicht erfüllt"),
}
"""An open Annex I question's two reading titles, by language (own-e-09 is English, own-e-10
German)."""


def annex_i_open_fact(given: HighRiskAnswer) -> str | None:
    """The key fact the model's Annex I answer holds open in law, as the node reads it (None when
    settled, or open on no fact its point reads); the step itself doesn't name it."""
    return open_field(given.annex_i, annex_i_facts(given.annex_i.point))


@pytest.mark.parametrize(
    ("point", "open_question", "on", "expected"),
    [
        pytest.param("annex:I:A:11", OPEN, "third_party_assessment", "third_party_assessment"),
        pytest.param(
            "annex:I:A:11", OPEN, "safety_component_or_product", "safety_component_or_product"
        ),
        pytest.param("annex:I:A:11", OPEN, NOT_NAMED, None, id="open-on-none"),
        pytest.param("annex:I:A:11", None, "third_party_assessment", None, id="settled-in-law"),
        pytest.param(None, OPEN, "third_party_assessment", None, id="no-point-reads-it"),
    ],
)
def test_the_screen_checks_open_fact_is_the_one_the_node_holds_open(
    point: str | None, open_question: OpenQuestion | None, on: str, expected: str | None
) -> None:
    """The screen check's open fact can fail: an answer open on another fact or on none, an
    answer settled in law, or one open on a fact no named point reads, holds no fact open (or
    another), whatever `open_on` names."""
    third_party = Answer.UNKNOWN
    given = answer(one=annex_i(point, YES, YES, third_party, open_question=open_question, on=on))
    assert annex_i_open_fact(given) == expected


def answers_read(monkeypatch: pytest.MonkeyPatch) -> list[HighRiskAnswer]:
    """Every model answer the high_risk node turns into its step, as `to_outcome` receives it."""
    seen: list[HighRiskAnswer] = []

    def spy(
        given: HighRiskAnswer, state: EngineState, found: Retrieved, library: HighRiskLibrary
    ) -> CheckOutcome:
        seen.append(given)
        return to_outcome(given, state, found, library)

    monkeypatch.setattr(node, "to_outcome", spy)
    return seen


def assert_the_screens_fields(
    result: CheckOutcome, given: HighRiskAnswer, run_state: EngineState, case: BenchmarkCase
) -> None:
    """E12's DoD on the recorded cases, after E9's citation check over the built corpus: the
    product-law question names the law, quotes Art. 6(1) and the Annex I entry, offers yes/no
    and knows what a yes settles; the open question is on the case's key fact (from the model's
    answer `given`) and has two structured readings whose quotes all pass the check."""
    checked = built_validator().check(result.step, run_state)
    assert not checked.unresolved
    step = with_checked_citations(result, checked, run_state["language"]).step
    if case.id in PRODUCT_LAW_QUESTIONS:
        asked, if_yes = PRODUCT_LAW_QUESTIONS[case.id]
        missing = step.missing_fact
        assert missing is not None
        assert missing.id == asked
        assert MEDICAL_DEVICES in missing.text
        assert [c.provision_id for c in missing.citations] == ["annex:I:A:11", "art:6:1"]
        assert missing.options == YES_NO
        assert missing.if_yes == if_yes
    if case.id in AMBIGUOUS_CASES and case.id not in KNOWN_GAPS:
        assert annex_i_open_fact(given) == AMBIGUOUS_CASES[case.id], given.annex_i.open_on
        question = step.open_question
        assert question is not None
        stricter, lenient = question.readings
        high_title, not_met_title = ANNEX_I_READING_TITLES[run_state["language"]]
        assert (stricter.title, stricter.risk_class, stricter.is_applied) == (
            high_title,
            RiskClass.HIGH_RISK,
            True,
        )
        assert (lenient.title, lenient.risk_class, lenient.is_applied) == (
            not_met_title,
            None,
            False,
        )
        for reading in question.readings:
            assert reading.citation is not None
            assert reading.citation in checked.verified
            assert reading.explanation and reading.consequence
        assert [item.kind for item in question.settled_by] == [SettledByKind.GUIDANCE]


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    ANNEX_I_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="no Annex I cases"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_replay_annex_i_case(
    case: BenchmarkCase, replay_check: HighRiskCheck, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each B5e case against its label and tags; a `KNOWN_GAPS` case is an expected failure."""
    run_state = replay_state(case, AS_OF)
    seen = answers_read(monkeypatch)
    result = replay_check(run_state)
    [given] = seen
    assert not unresolved_citations(result.step, run_state)
    assert not whole_articles(result.step)
    matches = high_risk_matches(result, case)
    step = result.step
    shown = (result.high_risk_route, result.annex_point, step.status, step.decision)
    assert_the_screens_fields(result, given, run_state, case)
    expect_known_gap(KNOWN_GAPS, result, case, matches=matches, shown=shown)
    assert matches, shown


# --- Replays under the original text (E11) -------------------------------------------------------
#
# One Omnibus-changed case per rule, replayed under the original text; the amended side of each
# pair is the case's `test_replay_annex_i_case`. Record them with `ORIGINAL_RECORD_COMMAND`.

ORIGINAL_RECORD_COMMAND = (
    "uv run pytest tests/engine/nodes/test_high_risk.py -k replay_original --record-mode=once"
)
"""Records only the original-text replays; `RECORD_COMMAND` (`-k replay`) would read the live
corpus again for every replay."""


@pytest.fixture
def original_replay_check(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[HighRiskCheck]:
    """`replay_check` for the original-text replays, whose skip names their own command."""
    with _recorded_check(
        luna_settings, record_mode, vcr_cassette_dir, default_cassette_name, ORIGINAL_RECORD_COMMAND
    ) as check:
        yield check


def _original_replay(case_id: str, replay_check: HighRiskCheck) -> CheckOutcome:
    """The case's high-risk step under the original text, its citations checked."""
    case = next((c for c in ANNEX_I_CASES if c.id == case_id), None)
    if case is None:
        pytest.skip(f"{case_id} is not in {ANNEX_I_CASES_DIR}")
    run_state: EngineState = {**replay_state(case, AS_OF), "law_version": LawVersion.ORIGINAL}
    result = replay_check(run_state)
    assert not unresolved_citations(result.step, run_state)
    assert not whole_articles(result.step)
    return result


@pytest.mark.vcr
def test_replay_original_machinery_guard_is_annex_i_section_a(
    original_replay_check: HighRiskCheck,
) -> None:
    """own-e-04's crane load limiter is machinery: Annex I B.21 under the amended text, with
    Art. 2(2); under the original text the machinery law is A.1, so it is high-risk with its AI
    Act duties and no Art. 2(2)."""
    result = _original_replay("own-e-04-loader-crane-tip-guard", original_replay_check)
    step = result.step
    shown = (result.high_risk_route, result.annex_point, step.status, step.decision)
    assert result.high_risk_route is HighRiskRoute.ANNEX_I, shown
    assert result.annex_point == "annex:I:A:1", shown
    assert step.status is Status.DECIDED, shown
    assert "art:2:2" not in cited(result), shown
    assert "Art. 2 Abs. 2" not in step.decision, shown  # the case is German


@pytest.mark.vcr
def test_replay_original_radio_check_reads_no_art_6_1a_to_1c(
    original_replay_check: HighRiskCheck,
) -> None:
    """own-e-06's speaker: under the amended text Art. 6(1c) (a radio-only notified body) and
    6(1a) (a convenience feature) keep it out of Annex I. The original text has neither: its
    assistant is still no safety component (Art. 3(14)), so it stays not high-risk, but the
    decision names no paragraph the Omnibus added."""
    result = _original_replay("own-e-06-smart-speaker-radio-check", original_replay_check)
    step = result.step
    shown = (result.high_risk_route, result.annex_point, step.status, step.decision)
    assert result.high_risk_route is None, shown
    assert not result.annex_iii_exempt, shown
    assert step.status is Status.DECIDED, shown
    assert not any(name in step.decision for name in OMNIBUS_PARAGRAPHS), shown


# --- E18 fixtures: the high-risk over-strictness causes (H4, H5, H6), and H4's positive side ---
#
# Record them with `E18_RECORD_COMMAND`.

E18_RECORD_COMMAND = (
    "uv run pytest tests/engine/nodes/test_high_risk.py -k 'e18_negative or e18_positive' "
    "--record-mode=once"
)
E18_CASES = [*negative_cases("h4"), *negative_cases("h5"), *negative_cases("h6")]
NOT_THE_ROUTE: dict[str, str] = {
    "fixture-e18-h4-water-demand-forecast": "annex:III:2",
    "fixture-e18-h5-choir-practice-app": "annex:I:A:6",
    "fixture-e18-h6-trade-fair-roundtables": "annex:III:1:b",
}
"""E18's causes, by fixture: the point the step must not read as the system's. H4: a planning
forecast is no safety component of critical infrastructure (Art. 3(14), recital 55). H5: an app
on others' phones is neither radio equipment nor its safety component (Art. 6(1)(a)). H6: grouping
people by what they type into a form is no biometric categorisation by sensitive attributes."""


@pytest.fixture
def e18_replay_check(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[HighRiskCheck]:
    """`replay_check` for the E18 fixtures: a missing recording raises `RecordingPendingError`
    (their strict xfail) rather than skipping."""
    require_recording(vcr_cassette_dir, default_cassette_name, record_mode)
    with _recorded_check(
        luna_settings, record_mode, vcr_cassette_dir, default_cassette_name, E18_RECORD_COMMAND
    ) as check:
        yield check


@pytest.mark.vcr
@pytest.mark.parametrize("case", E18_CASES, ids=lambda case: case.id)
def test_e18_negative_replay(case: BenchmarkCase, e18_replay_check: HighRiskCheck) -> None:
    """Each fixture is decided not high-risk, with no Art. 6(3) exemption, and its step neither
    routes through nor cites the point its cause wrongly read."""
    run_state = replay_state(case, AS_OF)
    result = e18_replay_check(run_state)
    assert not unresolved_citations(result.step, run_state)
    assert not whole_articles(result.step)
    step = result.step
    shown = (result.high_risk_route, result.annex_point, step.status, cited(result), step.decision)
    assert result.high_risk_route is None, shown
    assert not result.annex_iii_exempt, shown
    assert step.status is Status.DECIDED, shown
    assert NOT_THE_ROUTE[case.id] not in cited(result), shown


E18_POSITIVE_CASES = negative_cases("h4-positive")
"""H4's counterweight: a component on a road bridge whose own output detects that a load-bearing
part needs inspection, and closes the lane until it is done, is a safety component (guide-annex-iii
para 184(b) and (c)), so the H4 rule must keep it under Annex III point 2."""


@pytest.mark.vcr
@pytest.mark.parametrize("case", E18_POSITIVE_CASES, ids=lambda case: case.id)
def test_e18_positive_replay(case: BenchmarkCase, e18_replay_check: HighRiskCheck) -> None:
    """The H4 counterpart is decided high-risk through Annex III point 2, with no Art. 6(3)
    exemption."""
    run_state = replay_state(case, AS_OF)
    result = e18_replay_check(run_state)
    assert not unresolved_citations(result.step, run_state)
    assert not whole_articles(result.step)
    step = result.step
    shown = (result.high_risk_route, result.annex_point, step.status, cited(result), step.decision)
    assert result.high_risk_route is HighRiskRoute.ANNEX_III, shown
    assert result.annex_point == "annex:III:2", shown
    assert not result.annex_iii_exempt, shown
    assert step.status is Status.DECIDED, shown


def test_h4_has_its_positive_fixture() -> None:
    assert [case.id for case in E18_POSITIVE_CASES] == [
        "fixture-e18-h4-positive-bridge-bearing-wear"
    ]


E18_RULES = (
    # H6 (Annex III point 1(b), Art. 3(40); guide-annex-iii para 167)
    "- 1(b) is biometric categorisation according to sensitive or protected attributes",
    "(those protected under Art. 9(1) GDPR, such as racial or ethnic origin, political opinions, "
    "religious or philosophical beliefs, trade union membership, health, sex life or sexual "
    "orientation)",
    "Biometric data includes behavioural data such as keystroke patterns or gait.",
    "Grouping people by data that is not biometric data (what they enter or buy, their clothes or "
    "their social media activity), or by attributes that are not sensitive or protected, is not "
    "point 1(b).",
    # H4 (Annex III point 2, Art. 3(14); guide-annex-iii para 184, ex:065, ex:068)
    "- 2 needs a safety component (Art. 3(14))",
    'is not one: answer `uses` "no" for point 2.',
    "Decide by what the system's own output does.",
    "A component in the infrastructure whose output detects a dangerous situation that may "
    "directly lead to physical harm to natural persons or damage to property, or detects the need "
    "for maintenance or inspection whose omission may directly lead to such harm or damage, is a "
    "safety component, and so is one whose output prevents, controls or limits such harm (for "
    'example by stopping an operation): answer `uses` "yes" for point 2.',
    "A component used solely for cybersecurity purposes is not a safety component (recital 55).",
    # H5 (Art. 6(1)(a), Annex I Section A point 6)
    "The Radio Equipment Directive (`annex:I:A:6`) is the AI system's route only when",
    "Software supplied on its own that only runs on, or connects to, a phone, a router or another "
    "radio device made by others",
    "is neither: answer `point` null unless other listed legislation covers it.",
)
"""E18's H6, H4 and H5 rules with their supporting clauses, as high_risk.md words them."""


def test_the_prompt_states_the_e18_rules() -> None:
    flat = " ".join(node.HIGH_RISK_INSTRUCTIONS.split())
    for rule in E18_RULES:
        assert rule in flat


def test_each_high_risk_cause_has_its_fixture() -> None:
    assert [case.id for case in E18_CASES] == list(NOT_THE_ROUTE)


# --- E19: own/f, the larger over-strict groups on Annex III (B15's cases) ----------------------
#
# B15's Annex III negatives and their profiling counterpart: H1 (own-f-01, 02: the area but not
# the listed use or user), H2 (own-f-03, 04, 05: an Art. 6(3) condition met on the facts), H3
# (own-f-06: evaluating workers is profiling, so high-risk) and H4 (own-f-07, 08, 09: no safety
# component of critical infrastructure).

OWN_F_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "f"
OWN_F_CASES = [
    case for path in sorted(OWN_F_CASES_DIR.glob("*.yaml")) for case in load_yaml_file(path)
]
OWN_F_RECORD_COMMAND = (
    "uv run pytest tests/engine/nodes/test_high_risk.py -k own_f_replay --record-mode=once"
)


@pytest.fixture
def own_f_replay_check(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[HighRiskCheck]:
    """`replay_check` for own/f: a missing recording raises `RecordingPendingError` (its strict
    xfail) rather than skipping."""
    require_recording(vcr_cassette_dir, default_cassette_name, record_mode)
    with _recorded_check(
        luna_settings, record_mode, vcr_cassette_dir, default_cassette_name, OWN_F_RECORD_COMMAND
    ) as check:
        yield check


def _assumes_high_risk_on_point_2(result: CheckOutcome, case: BenchmarkCase) -> bool:
    """High-risk assumed on Annex III point 2 until a fact is answered: over-strict, never a
    false low risk."""
    return (
        result.step.status is Status.NEEDS_MORE_INFORMATION
        and result.high_risk_route is HighRiskRoute.ANNEX_III
        and result.annex_point == "annex:III:2"
    )


OWN_F_KNOWN_GAPS: dict[str, KnownGap] = {
    "own-f-07-water-mains-renewal-plan": KnownGap(
        "E20's re-record (2026-10-13): Annex III point 2 is assumed until the utility says "
        "whether it is a critical entity under the CER Directive (the retrieved guideline "
        "passage, para 198), against the H4 rule that a tool planning investment is no safety "
        "component (minimal_risk label); over-strict, not a false low risk. Run-to-run "
        "variance: E19's recording read `uses` 'no' on a request that differs only by E20's "
        "exemption rule, which is about the Annex I conformity route, not point 2",
        _assumes_high_risk_on_point_2,
    ),
}
"""own/f cases whose recorded outcome differs from the label (`KNOWN_GAPS`, for own/f)."""


@pytest.mark.vcr
@pytest.mark.parametrize("case", OWN_F_CASES, ids=lambda case: case.id)
def test_own_f_replay(case: BenchmarkCase, own_f_replay_check: HighRiskCheck) -> None:
    """Each own/f case against its label: never high-risk on an area alone, an Art. 6(3)
    condition applied to the facts rather than held open, profiling kept high-risk; an
    `OWN_F_KNOWN_GAPS` case is an expected failure."""
    run_state = replay_state(case, AS_OF)
    result = own_f_replay_check(run_state)
    assert not unresolved_citations(result.step, run_state)
    assert not whole_articles(result.step)
    step = result.step
    shown = (result.high_risk_route, result.annex_point, step.status, cited(result), step.decision)
    matches = high_risk_or_exempt_matches(result, case)
    expect_known_gap(OWN_F_KNOWN_GAPS, result, case, matches=matches, shown=shown)
    assert matches, shown


def test_own_f_holds_b15s_nine_cases() -> None:
    """The replay's set: B15's nine Annex III cases, each cause with its cases."""
    assert [case.id[: len("own-f-01")] for case in OWN_F_CASES] == [
        f"own-f-{n:02d}" for n in range(1, 10)
    ]
    tags = [tag for case in OWN_F_CASES for tag in case.tags if tag.startswith("trap:")]
    assert tags.count(EXEMPTION_TRAP) == 3
    assert tags.count("trap:annex_iii_area_not_use") == 2
    assert tags.count("trap:art_6_3_profiling") == 1
    assert tags.count("trap:critical_infrastructure_not_safety_component") == 3


E19_RULES = (
    # The bar for an open question of law, and the open fact named (B1)
    'An open question of law has a bar. Answer a route\'s `settled_in_law` "no" only when you '
    "can name the condition of Article 6 or of the Annex point whose reading is undecided for "
    "these facts",
    'being unsure, or wanting to be safe, is never a reason to answer "no".',
    'A fact the description leaves open is answered "unknown", and the application asks for it.',
    'answer that route\'s `settled_in_law` "no" and name the key fact the question is about in '
    "its `open_on`.",
    'annex_iii and annex_i then add `open_on`: when `settled_in_law` is "no", the key fact the '
    "open question is about, by its field name",
    # H1 (guide-annex-iii paras 65, 72, 81)
    "An Annex III point covers the use case it lists, not its whole area: only a limited set of "
    "use cases within the broad areas is high-risk, and the list of them is exhaustive "
    "(guidelines, paragraph 65).",
    "directly or indirectly, in the way the point lists, whether that is its only purpose or one "
    "among several purposes (paragraph 72).",
    "A point that names its user (5(a), 6, 7, 8(a)) doesn't apply to a system used by anyone "
    'else: answer `public_authority` "no".',
    "does not act on behalf of a public authority (paragraph 81).",
    # H2 (Art. 6(3), recital 53; guide-annex-iii paras 88-108)
    "Apply the conditions to the facts the description gives, and answer in `condition` the one "
    "the system's task meets.",
    # H3 (Art. 3(52), Art. 4(4) GDPR; guide-annex-iii paras 110-112)
    "Where personal data are processed without an evaluation of personal characteristics, which "
    "always includes a prediction, assessment or judgement about the person, there is no "
    "profiling;",
    "a simple classification of people by characteristics such as age, sex or height does not "
    "necessarily amount to profiling, as that depends on the purpose of the classification",
)
"""E19's bar and its H1-H3 rules, as high_risk.md words them."""

DROPPED_RULES = (
    "stricter reading",
    "stricter way",
    "whatever `settled_in_law` says",
    "not a question of law",
    "intended purpose is that use",
    "forecasting totals",
    "matching or filing",
    "decisions or totals",
)
"""Wording E19's fix round dropped: the stricter reading is code's (B4), Art. 6(3) is applied
to the facts without calling it a question of fact or law (F3), and the examples that came close
to B15's own/f cases give way to the guidelines' wording (F1, F7)."""


def test_the_prompt_states_the_e19_rules() -> None:
    flat = " ".join(node.HIGH_RISK_INSTRUCTIONS.split())
    for rule in E19_RULES:
        assert rule in flat
    for dropped in DROPPED_RULES:
        assert dropped not in flat


E20_RULE = (
    "An exemption from that legislation's conformity procedure that the company relies on (for "
    'example an in-house or own-use exemption, or a derogation) is never "no" by itself. While '
    "the description doesn't show that the exemption's conditions are met, answer \"unknown\". "
    'Once it does, whether Art. 6(1)(b) still applies is open in law: the product "is required '
    "to undergo a third-party conformity assessment\" can mean the product's class under that "
    'legislation or the product as the company handles it. Answer `settled_in_law` "no" and '
    '`open_on` "third_party_assessment".'
)
"""E20's rule on an exemption from the sector law's conformity procedure (decision 035 follow-up
2), as high_risk.md words it: Art. 6(1)(b)'s "is required to undergo" read both ways."""
E20_ORIGINAL_RULE = (
    "An exemption from that legislation's conformity procedure that the company relies on is "
    'read as the instructions say: never "no" by itself.'
)
"""The same rule kept under the original text, whose overlay redefines `third_party_assessment`."""


def test_the_prompt_states_the_e20_exemption_rule() -> None:
    """The rule sits in `third_party_assessment`, after its definition and before the next
    section, and the original text's overlay keeps it."""
    flat = " ".join(node.HIGH_RISK_INSTRUCTIONS.split())
    assert E20_RULE in flat
    start = flat.index("- `third_party_assessment`:")
    assert start < flat.index(E20_RULE) < flat.index("## question")
    assert E20_ORIGINAL_RULE in " ".join(node.ORIGINAL_INSTRUCTIONS.split())
