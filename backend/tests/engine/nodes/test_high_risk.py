"""The high-risk node (E5): Art. 6 applied to invented answers, the retrieval it runs (the
exclude filter, the German fallback, the candidates), the model call with a fake model, and the
replays of INIT's worked example and the Annex I own cases.

The unit-test descriptions and answers are invented, not benchmark cases. The replays read the
own cases from `eval/cases/own/e/` and replay recorded model answers; the corpus answers the
recording run saw are stored next to each cassette (`<cassette>.corpus.json`), so a replay needs
neither the database nor the network.
"""

import json
from collections.abc import Callable, Collection, Iterator, Sequence
from datetime import date
from functools import partial
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes import high_risk as node
from aiact.engine.nodes.high_risk import (
    AnnexIAnswer,
    AnnexIIIAnswer,
    Art63Answer,
    Art63Condition,
    HighRiskAnswer,
    HighRiskCheck,
    HighRiskOutputError,
    Lookup,
    Retrieved,
    Searcher,
    Settled,
    law_title,
    retrieve,
    to_outcome,
)
from aiact.engine.nodes.key_facts import Answer
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, CaseSet, load_yaml_file
from aiact.llm import LLMConfigError
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
LAW_HITS = (hit("art:26:1"), hit("annex:III:4:a"), hit("annex:III:4:b"), hit("art:6:3"))
GUIDE_HITS = (hit(EXAMPLE), hit("guide:guide-high-risk-annex-iii:para:010"))


class FakeSearch:
    """Records every call; returns `law` for the law and `guidance[language]` for guidelines."""

    def __init__(
        self,
        law: Sequence[SearchHit] = LAW_HITS,
        guidance: dict[Language, Sequence[SearchHit]] | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._law = tuple(law)
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
        doc_types = kwargs["doc_types"]
        assert isinstance(doc_types, Collection)
        hits = self._law if "law" in doc_types else tuple(self._guidance.get(language, ()))
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
    return retrieve(state(language=language), FakeSearch(), fake_lookup)


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
    return to_outcome(given, state(language=language), retrieved(language), fake_lookup)


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


def test_no_art_6_3_condition_means_high_risk() -> None:
    result = outcome(answer(RANKS_APPLICANTS))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert "None of the Art. 6(3) conditions applies" in result.step.decision


def test_a_condition_without_profiling_exempts_under_art_6_3() -> None:
    result = outcome(answer(RANKS_APPLICANTS, art_6_3(Art63Condition.A, profiling=Answer.NO)))
    assert result.high_risk_route is None
    assert result.annex_iii_exempt
    assert result.annex_point == "annex:III:4:a"
    assert result.step.status is Status.DECIDED
    assert {"art:6:3:a", "art:6:4"} <= set(cited(result))
    assert "Art. 6(3)(a)" in result.step.decision


def test_unknown_profiling_under_a_condition_assumes_high_risk_and_asks() -> None:
    result = outcome(answer(RANKS_APPLICANTS, art_6_3(Art63Condition.B, Answer.UNKNOWN)))
    assert result.high_risk_route is HighRiskRoute.ANNEX_III
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "profiling"
    assert question_ids(result)[0] == "profiling"
    assert "Assumed high-risk on the Annex III route" in result.step.decision


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
    with pytest.raises(HighRiskOutputError, match="Annex III point"):
        outcome(answer(annex_iii("annex:III:9", YES)))


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


def test_an_annex_i_point_without_a_text_is_a_broken_output() -> None:
    with pytest.raises(HighRiskOutputError, match="Annex I point"):
        outcome(answer(one=annex_i("annex:I:A:1", YES, YES, YES)))


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
    check = HighRiskCheck(_settings(), chat=_fake_chat(answer(RANKS_APPLICANTS)), search=search)
    check(state(language=Language.DE, exclude=EXCLUDED))
    assert len(search.calls) == 3  # law, guidance in German, guidance in English
    for call in search.calls:
        assert call["exclude_source_example_ids"] == EXCLUDED
        assert call["max_distance"] is None
        assert "include_held_out" not in call


def test_the_default_searcher_hands_the_filter_to_search_ai_act(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def spy(query: str, *args: object, **kwargs: object) -> SearchResults:
        seen.update(kwargs)
        return FakeSearch()(query, Language.EN, LawVersion.AMENDED, AS_OF, **kwargs)

    monkeypatch.setattr(node, "search_ai_act", spy)
    node.search_corpus(
        "query",
        Language.EN,
        LawVersion.AMENDED,
        AS_OF,
        doc_types={"law"},
        exclude_source_example_ids=EXCLUDED,
        max_distance=None,
        limit=5,
    )
    assert seen["exclude_source_example_ids"] == EXCLUDED
    assert seen["max_distance"] is None
    assert "include_held_out" not in seen


def test_german_guidance_falls_back_to_english_and_is_marked_english_only() -> None:
    search = FakeSearch(guidance={Language.EN: GUIDE_HITS})
    found = retrieve(state(language=Language.DE), search, fake_lookup)
    assert [call["language"] for call in search.calls] == [Language.DE, Language.DE, Language.EN]
    assert found.guidance == GUIDE_HITS
    result = to_outcome(
        answer(annex_iii("annex:III:4:a", YES, examples=(EXAMPLE,))),
        state(language=Language.DE),
        found,
        fake_lookup,
    )
    guidance = [c for c in result.step.citations if c.provision_id == EXAMPLE]
    assert len(guidance) == 1
    assert guidance[0].english_only
    assert guidance[0].document_status is DocumentStatus.DRAFT


def test_german_guidance_found_in_german_is_not_searched_again() -> None:
    german = (hit("guide:guide-definition:para:001", Language.DE),)
    search = FakeSearch(guidance={Language.DE: german})
    assert retrieve(state(language=Language.DE), search, fake_lookup).guidance == german
    assert len(search.calls) == 2


def test_only_annex_iii_rows_are_candidates() -> None:
    found = retrieved()
    assert [h.provision_id for h in found.annex_iii] == ["annex:III:4:a", "annex:III:4:b"]
    assert [p.provision_id for p in found.annex_i] == list(ANNEX_I_TEXT)


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
    retrieve(state(law_version=LawVersion.ORIGINAL), search, fake_lookup)
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
    assert human.index("Annex I:") < human.index("Annex III points found:")
    assert human.index("Text of annex:III:4:a.") < human.index("Description:")
    assert human.endswith(WORKED_EXAMPLE)
    assert "art:26:1" not in human


def test_the_check_runs_in_the_graph_and_sets_its_findings() -> None:
    check = HighRiskCheck(
        _settings(),
        chat=_fake_chat(answer(one=MEDICAL_DEVICE)),
        search=FakeSearch(),
        lookup=fake_lookup,
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
    check = HighRiskCheck(
        _settings(), chat=_fake_chat('{"annex_iii": {}}'), search=FakeSearch(), lookup=fake_lookup
    )
    with pytest.raises(HighRiskOutputError, match="doesn't fit the schema"):
        check(state())


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
    """The corpus answers of one replay: recorded from the real search and lookup while
    recording, served from `<cassette>.corpus.json` while replaying. A call the recording never
    saw (a changed query, filter or exclusion) fails the replay."""

    def __init__(self, path: Path, is_recording: bool) -> None:
        self._path = path
        self._is_recording = is_recording
        self._entries: dict[str, object] = (
            {} if is_recording else json.loads(path.read_text(encoding="utf-8"))
        )

    def _answer(self, call: dict[str, object], live: Callable[[], object]) -> object:
        key = json.dumps(call, sort_keys=True, default=str)
        if self._is_recording:
            try:
                result = live()
            except ProvisionNotFoundError:
                self._entries[key] = {NOT_FOUND: True}
                raise
            assert isinstance(result, SearchResults | Provision)
            self._entries[key] = result.model_dump(mode="json")
            return result
        if key not in self._entries:
            pytest.fail(f"no recorded corpus answer for {key}; record the replay again")
        entry = self._entries[key]
        if isinstance(entry, dict) and entry.get(NOT_FOUND):
            raise ProvisionNotFoundError(f"recorded as not found: {key}")
        return entry

    def search(self) -> Searcher:
        def run(
            query: str,
            language: Language,
            law_version: LawVersion,
            as_of: date | None,
            **options: object,
        ) -> SearchResults:
            shown = {k: sorted(v) if isinstance(v, set) else v for k, v in options.items()}
            call = {"search": query, "language": language, "law_version": law_version, **shown}
            call["as_of"] = as_of
            live = partial(node.search_corpus, query, language, law_version, as_of, **options)
            return SearchResults.model_validate(self._answer(call, live))

        return run

    def lookup(self) -> Lookup:
        def run(
            provision_id: str, language: Language, law_version: LawVersion, as_of: date | None
        ) -> Provision:
            call = {"lookup": provision_id, "language": language, "law_version": law_version}
            call["as_of"] = as_of
            live = partial(node.lookup_provision, provision_id, language, law_version, as_of)
            return Provision.model_validate(self._answer(call, live))

        return run

    def save(self) -> None:
        if self._is_recording:
            text = json.dumps(self._entries, indent=1, sort_keys=True, ensure_ascii=False)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(text + "\n", encoding="utf-8")


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
    recording = CorpusRecording(corpus, is_recording)
    yield HighRiskCheck(luna_settings, search=recording.search(), lookup=recording.lookup())
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


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    ANNEX_I_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="no Annex I cases"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_replay_annex_i_case(case: BenchmarkCase, replay_check: HighRiskCheck) -> None:
    """Each B5e case's class, route, Annex point and step status, from its label and tags."""
    label = case.label
    assert isinstance(label, CaseLabel)
    result = replay_check(state(case.description, case.language))
    if label.risk_class is not RiskClass.HIGH_RISK:
        assert result.high_risk_route is None
        assert not result.annex_iii_exempt
        assert result.step.status is label.status
        return
    also_iii = "annex_iii" in _tag(case, "also_route")
    expected = HighRiskRoute.ANNEX_III if also_iii else HighRiskRoute.ANNEX_I
    assert result.high_risk_route is expected
    points = {*_tag(case, "annex_i_point"), *([label.annex_point] if label.annex_point else [])}
    assert result.annex_point in points
    assert result.step.status is label.status
    for missing in _tag(case, "missing_fact"):
        assert result.step.missing_fact is not None
        assert result.step.missing_fact.id == missing
    if "b" in _tag(case, "annex_i_section") and label.status is Status.DECIDED:
        assert "2(2)" in result.step.decision or "Art. 2 Abs. 2" in result.step.decision
