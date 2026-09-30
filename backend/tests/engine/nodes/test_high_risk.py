"""The high-risk node (E5): Art. 6 applied to invented answers, the retrieval it runs (the
exclude filter, the German fallback, the candidates), the model call with a fake model, and the
replays of INIT's worked example and the Annex I own cases.

The unit-test descriptions and answers are invented, not benchmark cases. The replays read the
own cases from `eval/cases/own/e/` and replay recorded model answers; the corpus answers the
recording run saw are stored next to each cassette (`<cassette>.corpus.json`), so a replay needs
neither the database nor the network.
"""

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import cast

import psycopg
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field, SecretStr

from aiact.db import connect
from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes import high_risk as node
from aiact.engine.nodes import high_risk_retrieval as retrieval
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.high_risk import (
    AnnexIAnswer,
    AnnexIIIAnswer,
    Art63Answer,
    Art63Condition,
    HighRiskAnswer,
    HighRiskCheck,
    HighRiskOutputError,
    Settled,
    law_title,
    to_outcome,
)
from aiact.engine.nodes.high_risk_retrieval import (
    ANNEX_III_POINTS,
    HighRiskCorpus,
    HighRiskLibrary,
    Retrieved,
    retrieve,
)
from aiact.engine.nodes.key_facts import Answer
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, CaseSet, load_yaml_file
from aiact.llm import LLMConfigError, OpenRouterEmbeddings
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    DocumentStatus,
    EvidenceTag,
    FollowUpQuestion,
    HighRiskRoute,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    Status,
    StepName,
)
from aiact.settings import Settings

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
AS_OF = date(2026, 9, 30)
WORKED_EXAMPLE = (
    "We're a 40-person logistics company. We use a tool that reads incoming job applications, "
    "scores them, and shows HR a ranked shortlist. We bought it from a vendor and didn't "
    "change it."
)
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
DE_ANNEX_I_TEXT = {
    "annex:I:A:11": "11. Verordnung (EU) 2017/745 des Europäischen Parlaments und des Rates vom 5. "
    "April 2017 über Medizinprodukte, zur Änderung der Richtlinie 2001/83/EG (ABl. L 117);",
}


# --- Fakes ---------------------------------------------------------------------------------------


def provision(pid: str, text: str | None = None, language: Language = Language.EN) -> Provision:
    return Provision(
        provision_id=pid,
        doc_key="ai-act-consolidated",
        document_title="AI Act (consolidated)",
        doc_type="law",
        law_version=LawVersion.AMENDED,
        status=DocumentStatus.CONSOLIDATED,
        language=language,
        english_only=False,
        heading=None,
        text=text or f"Text of {pid}.",
        valid_from=date(2026, 7, 27),
        valid_to=None,
        disclaimer=DISCLAIMER[language],
    )


def fake_lookup(
    provision_id: str, language: Language, law_version: LawVersion, as_of: date | None
) -> Provision:
    """Any art/annex id has a text; the Annex I points in the tables have their real titles."""
    table = DE_ANNEX_I_TEXT if language is Language.DE else ANNEX_I_TEXT
    if provision_id.startswith("annex:I:") and provision_id not in table:
        raise ProvisionNotFoundError(provision_id)
    return provision(provision_id, table.get(provision_id), language)


def hit(pid: str, language: Language = Language.EN, text: str | None = None) -> SearchHit:
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
        text=text or f"Text of {pid}.",
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
        "answers": {},
        "exclude_source_example_ids": exclude,
        "facts": (),
        "steps": (),
    }


def retrieved(language: Language = Language.EN) -> Retrieved:
    return retrieve(state(language=language), FakeLibrary())


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
) -> AnnexIIIAnswer:
    return AnnexIIIAnswer.model_validate(
        {
            "point": point,
            "uses": uses,
            "public_authority": public_authority,
            **_openness(open_question),
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
) -> AnnexIAnswer:
    return AnnexIAnswer.model_validate(
        {
            "point": point,
            "covered": covered,
            "safety_component_or_product": safety,
            "third_party_assessment": third_party,
            **_openness(open_question),
            "evidence": EvidenceTag.INFERRED,
            "fact": f"Annex I: {point or 'none'}",
            "fact_numbers": (),
        }
    )


def answer(
    iii: AnnexIIIAnswer | None = None,
    art63: Art63Answer | None = None,
    one: AnnexIAnswer | None = None,
    question: FollowUpQuestion | None = None,
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


def outcome(given: HighRiskAnswer, language: Language = Language.EN) -> CheckOutcome:
    return to_outcome(given, state(language=language), retrieved(language), FakeLibrary())


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
    own = FollowUpQuestion(id="output_use", text="Who reads the score?", about="high_risk")
    result = outcome(answer(annex_iii("annex:III:4:b", Answer.UNKNOWN), question=own))
    assert result.step.missing_fact == own
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
    assert result.step.open_question == OPEN
    assert result.step.missing_fact is None
    assert "pending legal review" in result.step.decision


def test_an_open_annex_i_route_stays_high_risk_even_when_its_facts_say_no() -> None:
    """The in-house pattern: no third-party assessment as stated, but the law leaves open
    whether that means Art. 6(1)(b) is not met. High-risk stays the working assumption."""
    one = annex_i("annex:I:A:11", YES, YES, Answer.NO, open_question=OPEN)
    result = outcome(answer(one=one))
    assert_ambiguous(result, HighRiskRoute.ANNEX_I)
    assert result.annex_point == "annex:I:A:11"


def test_an_open_annex_i_route_is_ambiguous_even_when_its_facts_all_read_yes() -> None:
    result = outcome(answer(one=annex_i("annex:I:A:11", YES, YES, YES, open_question=OPEN)))
    assert_ambiguous(result, HighRiskRoute.ANNEX_I)


def test_an_open_annex_iii_point_is_ambiguous_with_high_risk_assumed() -> None:
    iii = annex_iii("annex:III:4:a", Answer.NO, open_question=OPEN)
    result = outcome(answer(iii))
    assert_ambiguous(result, HighRiskRoute.ANNEX_III)
    assert {"annex:III:4:a", "art:6:2", "art:6:3"} <= set(cited(result))


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
        {**annex_i("annex:I:A:11", YES, YES, Answer.NO).model_dump(), "settled_in_law": "no"}
    )
    result = outcome(answer(one=one), language=Language.DE)
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    open_question = result.step.open_question
    assert open_question is not None
    assert open_question.question == node.OPEN_FALLBACK[Language.DE]["annex_i"][0]
    assert open_question.readings[0].startswith("Hochrisiko")


def test_no_route_is_a_decided_not_high_risk() -> None:
    result = outcome(answer())
    assert result.high_risk_route is None
    assert result.annex_point is None
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:6:1", "art:6:2"]
    assert result.follow_up_questions == ()


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

    monkeypatch.setattr(retrieval, "search_ai_act", spy)
    connection, embedder = cast(psycopg.Connection, object()), FakeEmbedder()
    library = HighRiskCorpus(connection, embedder)
    retrieve(state(language=Language.DE, exclude=EXCLUDED), _only_search(library))
    assert len(seen) == 2
    for kwargs in seen:
        assert kwargs["exclude_source_example_ids"] == EXCLUDED
        assert kwargs["max_distance"] is None
        assert kwargs["connection"] is connection
        assert kwargs["embedder"] is embedder
        assert "include_held_out" not in kwargs


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

    def spy(provision_id: str, *args: object, connection: object) -> Provision:
        seen.append(connection)
        return provision(provision_id)

    monkeypatch.setattr(retrieval, "get_provision", spy)
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

    def lookup(provision_id: str, *args: object, connection: FakeConnection) -> Provision:
        assert connection.is_open
        return fake_lookup(provision_id, *args)  # type: ignore[arg-type]

    def no_connection_open() -> None:
        assert not any(c.is_open for c in connections)

    monkeypatch.setattr(node, "connect", fake_connect)
    monkeypatch.setattr(node, "OpenRouterEmbeddings", Embeddings)
    monkeypatch.setattr(retrieval, "search_ai_act", search)
    monkeypatch.setattr(retrieval, "get_provision", lookup)
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
    sent = node.high_risk_response_format(_prompt_annex_i_ids(language))
    point = _point_schema(sent, "AnnexIIIAnswer")
    leaves = {"type": "string", "enum": _prompt_annex_iii_ids(language)}
    assert point == {"anyOf": [leaves, {"type": "null"}], "title": "Point"}


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
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **pinned)  # pyright: ignore[reportCallIssue]


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
            "answers": {},
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


def test_the_output_cap_leaves_room_for_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    """own-e-14 (both routes apply) spent all of 3000 output tokens on reasoning; 6000 fits."""
    asked: dict[str, object] = {}

    def spy(**kwargs: object) -> BaseChatModel:
        asked.update(kwargs)
        return _fake_chat(answer())

    monkeypatch.setattr(node, "engine_chat_model", spy)
    HighRiskCheck(_settings(), library=FakeLibrary())
    assert asked["max_tokens"] == 6000


def test_the_engine_model_must_be_pinned() -> None:
    with pytest.raises(LLMConfigError, match="ENGINE_PROVIDER"):
        HighRiskCheck(_settings(engine_provider=None))


def test_the_response_format_requires_every_field() -> None:
    schema = node.HIGH_RISK_RESPONSE_FORMAT["json_schema"]
    assert isinstance(schema, dict)
    assert schema["schema"]["required"] == ["annex_iii", "art_6_3", "annex_i", "question"]


def test_each_route_answers_its_legal_openness_right_after_its_facts() -> None:
    """Strict structured output fills fields in order, so `settled_in_law` and `open_question`
    sit after each route's facts and before its summary."""
    definitions = node.HIGH_RISK_RESPONSE_FORMAT["json_schema"]
    assert isinstance(definitions, dict)
    defs = definitions["schema"]["$defs"]
    last_facts = {
        "AnnexIIIAnswer": "public_authority",
        "Art63Answer": "profiling",
        "AnnexIAnswer": "third_party_assessment",
    }
    for name, last in last_facts.items():
        fields = defs[name]["required"]
        at = fields.index(last)
        assert fields[at + 1 : at + 4] == ["settled_in_law", "open_question", "evidence"]


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
    limited = node.high_risk_response_format(ids)
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
    point = _annex_i_point_schema(node.high_risk_response_format(ids))
    assert isinstance(point, dict)
    assert "annex:I:A:21" not in point["anyOf"][0]["enum"]


def test_no_annex_i_text_leaves_only_null() -> None:
    assert _annex_i_point_schema(node.high_risk_response_format([])) == {
        "anyOf": [{"type": "null"}],
        "title": "Point",
    }


def test_the_check_sends_the_limited_schema() -> None:
    content = answer(RANKS_APPLICANTS).model_dump_json()
    chat = RecordingChat(messages=iter([AIMessage(content=content)]))
    HighRiskCheck(_settings(), chat=chat, library=FakeLibrary())(state())
    [sent] = chat.formats
    assert sent == node.high_risk_response_format(_prompt_annex_i_ids(Language.EN))


# --- Replays: INIT's worked example and the Annex I own cases ------------------------------------
#
# Record (live model and embedding calls, and the local corpus; see the story report for the
# cost) with `uv run pytest tests/engine/nodes/test_high_risk.py -k replay --record-mode=once`.

ANNEX_I_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "e"


def _annex_i_cases() -> list[BenchmarkCase]:
    paths = sorted(ANNEX_I_CASES_DIR.rglob("*.yaml")) if ANNEX_I_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


ANNEX_I_CASES = _annex_i_cases()


NOT_FOUND = "not_found"
"""The entry of a lookup the corpus had no text for; the replay raises it again."""


class CorpusRecording:
    """A `HighRiskLibrary` for one replay: while recording it asks the real corpus (`live`) and
    keeps each answer; while replaying it serves them from `<cassette>.corpus.json`. A call the
    recording never saw (a changed query, filter or exclusion) fails the replay."""

    def __init__(self, path: Path, live: HighRiskCorpus | None) -> None:
        self._path = path
        self._live = live
        self._entries: dict[str, object] = (
            {} if live else json.loads(path.read_text(encoding="utf-8"))
        )

    def _answer(self, call: dict[str, object], ask: Callable[[HighRiskCorpus], object]) -> object:
        key = json.dumps(call, sort_keys=True, default=str)
        if self._live is not None:
            try:
                result = ask(self._live)
            except ProvisionNotFoundError:
                self._entries[key] = {NOT_FOUND: True}
                raise
            self._entries[key] = _dumped(result)
            return result
        if key not in self._entries:
            pytest.fail(f"no recorded corpus answer for {key}; record the replay again")
        entry = self._entries[key]
        if isinstance(entry, dict) and entry.get(NOT_FOUND):
            raise ProvisionNotFoundError(f"recorded as not found: {key}")
        return entry

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        call = {"lookup": provision_id, **_shown(lookup)}
        found = self._answer(call, lambda live: live.provision(provision_id, lookup))
        return Provision.model_validate(found)

    def search(
        self, query: str, lookup: Lookup, *, language: Language, doc_type: str, limit: int
    ) -> tuple[SearchHit, ...]:
        call = {"search": query, **_shown(lookup), "language": language, "doc_type": doc_type}
        call["limit"] = limit

        def ask(live: HighRiskCorpus) -> object:
            return live.search(query, lookup, language=language, doc_type=doc_type, limit=limit)

        found = self._answer(call, ask)
        assert isinstance(found, tuple | list)
        return tuple(SearchHit.model_validate(hit) for hit in found)

    def save(self) -> None:
        if self._live is not None:
            text = json.dumps(self._entries, indent=1, sort_keys=True, ensure_ascii=False)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(text + "\n", encoding="utf-8")


def _shown(lookup: Lookup) -> dict[str, object]:
    return {**asdict(lookup), "exclude_source_example_ids": list(lookup.exclude_source_example_ids)}


def _dumped(result: object) -> object:
    if isinstance(result, tuple):
        return [_dumped(item) for item in result]
    assert isinstance(result, SearchHit | Provision)
    return result.model_dump(mode="json")


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@pytest.fixture
def replay_check(
    luna_settings: Settings, record_mode: str, vcr_cassette_dir: str, default_cassette_name: str
) -> Iterator[HighRiskCheck]:
    """A `HighRiskCheck` over the recorded model and corpus; skips while nothing is recorded."""
    cassette = Path(vcr_cassette_dir) / f"{default_cassette_name}.yaml"
    corpus = cassette.with_suffix(".corpus.json")
    is_recording = record_mode != "none"
    if not is_recording and not (cassette.exists() and corpus.exists()):
        pytest.skip(
            f"{default_cassette_name} has no recording yet; record it with `uv run pytest "
            "tests/engine/nodes/test_high_risk.py -k replay --record-mode=once`"
        )
    if not is_recording:
        yield HighRiskCheck(luna_settings, library=CorpusRecording(corpus, None))
        return
    with connect() as connection:
        live = HighRiskCorpus(connection, OpenRouterEmbeddings(settings=luna_settings))
        recording = CorpusRecording(corpus, live)
        yield HighRiskCheck(luna_settings, library=recording)
        recording.save()


@pytest.mark.vcr
def test_replay_worked_example(replay_check: HighRiskCheck) -> None:
    """INIT's worked example: recruitment use, and ranking is profiling, so no Art. 6(3)."""
    result = replay_check(state())
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.annex_point == "annex:III:4:a"
    assert not result.annex_iii_exempt
    assert result.step.status is Status.DECIDED
    assert "art:6:3" in cited(result)


def _tag(case: BenchmarkCase, name: str) -> list[str]:
    prefix = f"{name}:"
    return [tag.removeprefix(prefix) for tag in case.tags if tag.startswith(prefix)]


@dataclass(frozen=True)
class KnownGap:
    reason: str
    reads: Callable[[CheckOutcome], bool]
    """The documented wrong reading; any other miss fails the replay."""


def _asks_for_third_party_assessment(result: CheckOutcome) -> bool:
    """High-risk assumed on the Annex I route, asking whether a third-party conformity assessment
    is required (Art. 6(1)(b))."""
    missing = result.step.missing_fact
    return (
        result.step.status is Status.NEEDS_MORE_INFORMATION
        and result.high_risk_route is HighRiskRoute.ANNEX_I
        and missing is not None
        and missing.id == "third_party_assessment"
        and missing.about == "art:6:1:b"
    )


KNOWN_GAPS: dict[str, KnownGap] = {
    "own-e-10-in-house-nodule-finder": KnownGap(
        "the model treats the MDR in-house exemption as a missing fact (it asks whether a "
        "third-party assessment is required) instead of an open legal question; the label stays "
        "legally_ambiguous and V8 scores it end to end (user, 2026-10-01)",
        _asks_for_third_party_assessment,
    ),
}
"""Recorded cases whose high-risk outcome differs from the label, with the reason and the
reading they give instead; each fails when it starts matching, so the entry is removed."""


def _matches_label(result: CheckOutcome, case: BenchmarkCase) -> bool:
    """The case's class, route, Annex point and step status, from its label and tags."""
    label = case.label
    assert isinstance(label, CaseLabel)
    step = result.step
    if label.risk_class is not RiskClass.HIGH_RISK:
        return (
            result.high_risk_route is None
            and not result.annex_iii_exempt
            and step.status is label.status
        )
    also_iii = "annex_iii" in _tag(case, "also_route")
    expected = HighRiskRoute.ANNEX_III if also_iii else HighRiskRoute.ANNEX_I
    points = {*_tag(case, "annex_i_point"), *([label.annex_point] if label.annex_point else [])}
    missing = _tag(case, "missing_fact")
    asked = step.missing_fact.id if step.missing_fact else None
    section_b_decided = "b" in _tag(case, "annex_i_section") and label.status is Status.DECIDED
    names_art_2_2 = "2(2)" in step.decision or "Art. 2 Abs. 2" in step.decision
    return (
        result.high_risk_route is expected
        and result.annex_point in points
        and step.status is label.status
        and all(asked == fact for fact in missing)
        and (names_art_2_2 or not section_b_decided)
    )


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    ANNEX_I_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="no Annex I cases"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_replay_annex_i_case(case: BenchmarkCase, replay_check: HighRiskCheck) -> None:
    """Each B5e case against its label and tags; a `KNOWN_GAPS` case is an expected failure."""
    result = replay_check(state(case.description, case.language))
    matches = _matches_label(result, case)
    gap = KNOWN_GAPS.get(case.id)
    if gap is not None:
        if matches:
            pytest.fail(f"{case.id} now matches its label; remove it from KNOWN_GAPS")
        assert gap.reads(result), (
            result.high_risk_route,
            result.step.status,
            result.step.decision,
        )
        pytest.xfail(gap.reason)
    step = result.step
    assert matches, (result.high_risk_route, result.annex_point, step.status, step.decision)
