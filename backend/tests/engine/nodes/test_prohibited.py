"""The prohibited node (E4): Art. 5 applied to invented answers (each practice, its exceptions,
the Art. 5(1)(h) conditions and the December 2026 dates), the retrieval it runs, the model call
with a fake model, and the B5c replays, which run once their recordings exist.

The unit-test descriptions and answers are invented, not benchmark cases. The replays read the
own cases from `eval/cases/own/c/` and replay recorded model answers; the corpus answers the
recording run saw are stored next to each cassette (`<cassette>.corpus.json`).
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from typing import cast

import psycopg
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.db import connect
from aiact.engine.graph import EngineNodes, build_graph
from aiact.engine.nodes import guideline_retrieval as retrieval
from aiact.engine.nodes import prohibited as node
from aiact.engine.nodes import prohibited_texts as texts
from aiact.engine.nodes.common import Lookup
from aiact.engine.nodes.guideline_retrieval import (
    GuidelineCorpus,
    GuidelineLibrary,
    Retrieved,
    retrieve,
)
from aiact.engine.nodes.key_facts import Answer, Settled
from aiact.engine.nodes.prohibited import ProhibitedCheck, ProhibitedOutputError, to_outcome
from aiact.engine.nodes.prohibited_practices import (
    DECEMBER_PROHIBITIONS_APPLY_FROM,
    BiometricCategorisationAnswer,
    CrimeRiskAnswer,
    EmotionAnswer,
    FaceScrapingAnswer,
    ManipulationAnswer,
    OpenCondition,
    PracticeSummary,
    ProhibitedAnswer,
    RbiObjective,
    RemoteIdentificationAnswer,
    SexualMaterialAnswer,
    SocialScoringAnswer,
    VulnerabilityAnswer,
)
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseSet, load_yaml_file
from aiact.eval.experiments.matchers import prohibited_matches, replay_state
from aiact.llm import LLMConfigError, OpenRouterEmbeddings
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.retrieval.search import SearchHit, SearchResults
from aiact.schemas import (
    DISCLAIMER,
    STEP_ORDER,
    DocumentStatus,
    EvidenceTag,
    Fact,
    Language,
    LawVersion,
    OpenQuestion,
    RiskClass,
    SourceSpan,
    Status,
    StepName,
)
from aiact.settings import Settings
from tests.engine.built_corpus import unresolved_citations
from tests.engine.nodes.corpus_recording import (
    RecordedGuidelineLibrary,
    corpus_recording,
)
from tests.engine.nodes.known_gaps import KnownGap, expect_known_gap, refused

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
AS_OF = date(2026, 9, 30)
BEFORE_DECEMBER = date(2026, 11, 16)
AFTER_DECEMBER = date(2026, 12, 15)
TOOL = "We run a call centre. A tool listens to our agents' calls and reports on them."
EXCLUDED = ("pr-ex-900",)
OPEN_HARM = OpenQuestion(
    question="Is the harm significant?", readings=("Yes, prohibited.", "No, not prohibited.")
)
GUIDE_HITS = ("guide:guide-prohibited:para:010", "guide:guide-prohibited:para:020")


# --- Fakes ---------------------------------------------------------------------------------------


def provision(pid: str, language: Language = Language.EN) -> Provision:
    return Provision(
        provision_id=pid,
        doc_key="ai-act-consolidated",
        document_title="AI Act (consolidated)",
        doc_type="law",
        law_version=LawVersion.AMENDED,
        status=DocumentStatus.CONSOLIDATED,
        language=language,
        english_only=False,
        heading="Article 5 — Prohibited AI practices",
        text=f"Text of {pid}.",
        valid_from=date(2026, 7, 27),
        valid_to=None,
        disclaimer=DISCLAIMER[language],
    )


def hit(pid: str, language: Language = Language.EN) -> SearchHit:
    return SearchHit(
        provision_id=pid,
        doc_key="guide-prohibited",
        document_title="Guidelines on prohibited AI practices",
        doc_type="guideline",
        law_version=None,
        status=DocumentStatus.FINAL,
        language=language,
        heading="A heading",
        text=f"Text of {pid}.",
        valid_from=date(2025, 2, 4),
        valid_to=None,
        score=0.03,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.6,
        keyword_idf=None,
    )


class FakeLibrary:
    """A `GuidelineLibrary` that records every call: any provision has a text except those in
    `missing`, and the guidance found in a language is `guidance[language]`."""

    def __init__(
        self,
        guidance: Mapping[Language, Sequence[str]] | None = None,
        missing: frozenset[str] = frozenset(),
    ) -> None:
        self.lookups: list[tuple[str, Lookup]] = []
        self.searches: list[tuple[str, Lookup, Language]] = []
        self._guidance = guidance if guidance is not None else {Language.EN: GUIDE_HITS}
        self._missing = missing

    def provision(self, provision_id: str, lookup: Lookup) -> Provision:
        self.lookups.append((provision_id, lookup))
        if provision_id in self._missing:
            raise ProvisionNotFoundError(provision_id)
        return provision(provision_id, lookup.language)

    def guidance(self, query: str, lookup: Lookup, *, language: Language) -> tuple[SearchHit, ...]:
        self.searches.append((query, lookup, language))
        return tuple(hit(pid, language) for pid in self._guidance.get(language, ()))


def state(
    as_of: date = AS_OF,
    language: Language = Language.EN,
    law_version: LawVersion = LawVersion.AMENDED,
    exclude: tuple[str, ...] = (),
    facts: tuple[Fact, ...] = (),
) -> EngineState:
    return {
        "description": TOOL,
        "language": language,
        "law_version": law_version,
        "as_of": as_of,
        "exclude_source_example_ids": exclude,
        "facts": facts,
        "steps": (),
    }


# --- Answers -------------------------------------------------------------------------------------


def part[P: PracticeSummary](model: type[P], **facts: object) -> P:
    """A practice's answer, settled in law: every key fact "no" unless given."""
    enums = {Answer: Answer.NO, RbiObjective: RbiObjective.NONE, OpenCondition: OpenCondition.NONE}
    defaults = {
        name: enums[field.annotation]
        for name, field in model.model_fields.items()
        if field.annotation in enums
    }
    return model.model_validate(
        {
            **defaults,
            **facts,
            "settled_in_law": Settled.YES,
            "open_question": None,
            "evidence": EvidenceTag.INFERRED,
            "fact": f"{model.__name__} reading.",
            "fact_numbers": (),
        }
    )


def unsettled[P: PracticeSummary](given: P, question: OpenQuestion = OPEN_HARM) -> P:
    """`given` with the law leaving it open, on `question`."""
    return given.model_copy(update={"settled_in_law": Settled.NO, "open_question": question})


def answer(*parts: PracticeSummary, guidance: tuple[int, ...] = ()) -> ProhibitedAnswer:
    """The whole answer: the parts given, and every other practice not raised."""
    given = {type(p): p for p in parts}
    fields = {
        name: given.get(cast(type[PracticeSummary], field.annotation))
        or part(cast(type[PracticeSummary], field.annotation))
        for name, field in ProhibitedAnswer.model_fields.items()
        if name != "guidance_numbers"
    }
    return ProhibitedAnswer.model_validate({**fields, "guidance_numbers": guidance})


def outcome(
    given: ProhibitedAnswer,
    at: EngineState | None = None,
    library: GuidelineLibrary | None = None,
) -> CheckOutcome:
    run = at or state()
    library = library or FakeLibrary()
    return to_outcome(given, run, retrieve(run, library, node.SOURCE.article), library)


def cited(result: CheckOutcome) -> list[str]:
    return [citation.provision_id for citation in result.step.citations]


WORKPLACE_EMOTIONS = part(
    EmotionAnswer, infers_emotions=Answer.YES, workplace_or_education=Answer.YES
)
UNDRESSING_APP = part(
    SexualMaterialAnswer, intimate_imagery=Answer.YES, generation_purpose=Answer.YES
)
POLICE_LIVE_SEARCH = {
    "real_time_identification": Answer.YES,
    "law_enforcement_use": Answer.YES,
    "objective": RbiObjective.VICTIMS,
    "national_law_authorisation": Answer.YES,
    "prior_authorisation": Answer.YES,
    "targeted_use": Answer.YES,
    "impact_assessment_registration": Answer.YES,
}


# --- Applying Art. 5 -----------------------------------------------------------------------------


def test_no_practice_raised_is_a_decided_no_match_citing_the_list() -> None:
    result = outcome(answer())
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert result.step.decision == "No prohibited practice under Art. 5 matches."
    assert cited(result) == ["art:5:1"]
    assert result.follow_up_questions == ()


def test_emotion_recognition_at_work_is_prohibited() -> None:
    result = outcome(answer(WORKPLACE_EMOTIONS))
    assert result.matched
    assert result.step.status is Status.DECIDED
    assert result.step.decision.startswith("Prohibited under Art. 5(1)(f).")
    assert cited(result) == ["art:5:1:f"]


def test_workplace_monitoring_asks_whether_it_infers_emotions() -> None:
    """B12's rule (academic-0096): at work, an open emotion question is asked, not guessed."""
    monitoring = part(
        EmotionAnswer, infers_emotions=Answer.UNKNOWN, workplace_or_education=Answer.YES
    )
    result = outcome(answer(monitoring))
    assert result.matched  # prohibited is the working assumption
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "infers_emotions"
    assert result.step.missing_fact.about == "art:5:1:f"
    assert [q.id for q in result.follow_up_questions] == ["infers_emotions"]


def test_emotions_outside_work_or_education_ask_nothing() -> None:
    callers = part(EmotionAnswer, infers_emotions=Answer.UNKNOWN)
    result = outcome(answer(callers))
    assert not result.matched
    assert result.step.status is Status.DECIDED


def test_the_safety_exception_takes_emotion_recognition_out_and_is_named() -> None:
    safety = part(
        EmotionAnswer,
        infers_emotions=Answer.YES,
        workplace_or_education=Answer.YES,
        medical_or_safety=Answer.YES,
    )
    result = outcome(answer(safety))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert "Considered Art. 5(1)(f): EmotionAnswer reading." in result.step.decision
    assert cited(result) == ["art:5:1:f"]


@pytest.mark.parametrize("model", [ManipulationAnswer, VulnerabilityAnswer])
def test_an_open_significant_harm_is_asked(
    model: type[ManipulationAnswer] | type[VulnerabilityAnswer],
) -> None:
    """B12's rule (academic-0005): significant harm is a deciding fact, never presumed."""
    gate = "manipulative_technique" if model is ManipulationAnswer else "exploits_vulnerability"
    facts = {gate: Answer.YES, "distorts_behaviour": Answer.YES}
    result = outcome(answer(part(model, significant_harm=Answer.UNKNOWN, **facts)))
    assert result.matched
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "significant_harm"


def test_significant_harm_the_law_leaves_open_is_ambiguous_with_prohibited_assumed() -> None:
    pressure = unsettled(
        part(
            ManipulationAnswer,
            manipulative_technique=Answer.YES,
            distorts_behaviour=Answer.YES,
            significant_harm=Answer.NO,
        )
    )
    result = outcome(answer(pressure))
    assert result.matched
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    assert result.step.open_question == OPEN_HARM
    assert "pending legal review: Is the harm significant?" in result.step.decision
    assert cited(result) == ["art:5:1:a"]


def test_an_unsettled_practice_without_its_question_gets_the_fixed_one() -> None:
    unsettled = part(ManipulationAnswer, manipulative_technique=Answer.YES)
    result = outcome(answer(unsettled.model_copy(update={"settled_in_law": Settled.NO})))
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    open_question = result.step.open_question
    assert open_question is not None
    assert "Art. 5(1)(a)" in open_question.question
    assert open_question.readings[0].startswith("Prohibited")


def test_an_unsettled_flag_on_a_practice_not_raised_changes_nothing() -> None:
    quiet = part(ManipulationAnswer).model_copy(update={"settled_in_law": Settled.NO})
    assert outcome(answer(quiet)).step.status is Status.DECIDED


@pytest.mark.parametrize(
    ("met", "open_on", "points"),
    [
        ("unrelated_context_treatment", OpenCondition.DISPROPORTIONATE, ["art:5:1:c:i"]),
        ("disproportionate_treatment", OpenCondition.UNRELATED_CONTEXT, ["art:5:1:c:ii"]),
    ],
)
def test_social_scoring_met_on_one_alternative_is_not_held_open_by_the_other(
    met: str, open_on: OpenCondition, points: list[str]
) -> None:
    """Art. 5(1)(c) needs (i) or (ii): with one met, an open other decides nothing (own-c-10)."""
    scoring = part(SocialScoringAnswer, social_scoring=Answer.YES, **{met: Answer.YES})
    result = outcome(answer(unsettled(scoring).model_copy(update={"open_on": open_on})))
    assert result.matched
    assert result.step.status is Status.DECIDED
    assert result.step.open_question is None
    assert cited(result) == ["art:5:1:c", *points]


def test_an_open_alternative_does_not_settle_an_unknown_social_scoring() -> None:
    scoring = part(
        SocialScoringAnswer,
        social_scoring=Answer.UNKNOWN,
        disproportionate_treatment=Answer.YES,
    )
    on_i = unsettled(scoring).model_copy(update={"open_on": OpenCondition.UNRELATED_CONTEXT})
    assert outcome(answer(on_i)).step.status is Status.LEGALLY_AMBIGUOUS


def test_an_open_alternative_with_the_other_not_met_stays_open() -> None:
    """own-c-11's reading: (ii) answered yes but open in law, (i) unknown: still open."""
    scoring = part(
        SocialScoringAnswer,
        social_scoring=Answer.YES,
        unrelated_context_treatment=Answer.UNKNOWN,
        disproportionate_treatment=Answer.YES,
    )
    on_ii = unsettled(scoring).model_copy(update={"open_on": OpenCondition.DISPROPORTIONATE})
    result = outcome(answer(on_ii))
    assert result.step.status is Status.LEGALLY_AMBIGUOUS


def test_an_open_question_on_social_scoring_itself_stays_open() -> None:
    scoring = part(
        SocialScoringAnswer,
        social_scoring=Answer.YES,
        unrelated_context_treatment=Answer.YES,
    )
    on_scoring = unsettled(scoring).model_copy(update={"open_on": OpenCondition.SOCIAL_SCORING})
    assert outcome(answer(on_scoring)).step.status is Status.LEGALLY_AMBIGUOUS


def test_social_scoring_with_neither_alternative_met_stays_open() -> None:
    scoring = part(SocialScoringAnswer, social_scoring=Answer.YES)
    result = outcome(answer(unsettled(scoring)))
    assert result.matched
    assert result.step.status is Status.LEGALLY_AMBIGUOUS


def test_a_met_practice_beats_an_open_one() -> None:
    pressure = unsettled(part(ManipulationAnswer, manipulative_technique=Answer.YES))
    result = outcome(answer(pressure, WORKPLACE_EMOTIONS))
    assert result.step.status is Status.DECIDED
    assert result.matched
    assert cited(result) == ["art:5:1:f"]


def test_an_open_practice_still_asks_the_open_facts_of_others() -> None:
    pressure = unsettled(part(ManipulationAnswer, manipulative_technique=Answer.YES))
    monitoring = part(
        EmotionAnswer, infers_emotions=Answer.UNKNOWN, workplace_or_education=Answer.YES
    )
    result = outcome(answer(pressure, monitoring))
    assert result.step.status is Status.LEGALLY_AMBIGUOUS
    assert result.step.missing_fact is None
    assert [q.id for q in result.follow_up_questions] == ["infers_emotions"]


@pytest.mark.parametrize(
    ("model", "facts", "point"),
    [
        (
            SocialScoringAnswer,
            {"social_scoring": Answer.YES, "unrelated_context_treatment": Answer.YES},
            ["art:5:1:c", "art:5:1:c:i"],
        ),
        (
            CrimeRiskAnswer,
            {"crime_risk_assessment": Answer.YES, "solely_profiling": Answer.YES},
            ["art:5:1:d"],
        ),
        (FaceScrapingAnswer, {"untargeted_face_scraping": Answer.YES}, ["art:5:1:e"]),
        (
            BiometricCategorisationAnswer,
            {"biometric_categorisation": Answer.YES, "sensitive_traits": Answer.YES},
            ["art:5:1:g"],
        ),
    ],
)
def test_each_practice_met_is_prohibited_and_cites_its_point(
    model: type[PracticeSummary], facts: dict[str, Answer], point: list[str]
) -> None:
    result = outcome(answer(part(model, **facts)))
    assert result.matched
    assert result.step.status is Status.DECIDED
    assert cited(result) == point


@pytest.mark.parametrize(
    ("model", "facts"),
    [
        (
            CrimeRiskAnswer,
            {
                "crime_risk_assessment": Answer.YES,
                "solely_profiling": Answer.YES,
                "fact_based_assessment": Answer.YES,
            },
        ),
        (
            BiometricCategorisationAnswer,
            {
                "biometric_categorisation": Answer.YES,
                "sensitive_traits": Answer.YES,
                "lawful_labelling": Answer.YES,
            },
        ),
        (SocialScoringAnswer, {"social_scoring": Answer.YES}),
    ],
)
def test_an_exception_or_a_missing_condition_rules_a_practice_out(
    model: type[PracticeSummary], facts: dict[str, Answer]
) -> None:
    result = outcome(answer(part(model, **facts)))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert "Considered" in result.step.decision


# --- Points (ba) and (bb) and their date -----------------------------------------------------


def test_an_undressing_app_after_2_december_2026_is_prohibited() -> None:
    result = outcome(answer(UNDRESSING_APP), state(as_of=AFTER_DECEMBER))
    assert result.matched
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:5:1:ba", "art:5:1a:a:i", "art:113:a"]


def test_the_same_app_before_2_december_2026_is_not_yet_prohibited() -> None:
    """Art. 113(a): (ba) applies from 2 December 2026; the step says so and cites the date."""
    result = outcome(answer(UNDRESSING_APP), state(as_of=BEFORE_DECEMBER))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    decision = result.step.decision
    assert decision.startswith("No prohibited practice under Art. 5 matches.")
    assert "Art. 5(1)(ba) applies only from 2 December 2026" in decision
    assert "on 16 November 2026" in decision
    assert "from 2 December 2026 it will apply" in decision
    assert cited(result) == ["art:5:1:ba", "art:5:1a:a:i", "art:113:a"]


def test_the_day_the_december_prohibitions_start_counts() -> None:
    result = outcome(answer(UNDRESSING_APP), state(as_of=date(2026, 12, 2)))
    assert result.matched
    day_before = outcome(answer(UNDRESSING_APP), state(as_of=date(2026, 12, 1)))
    assert not day_before.matched


def test_the_start_date_is_written_in_german() -> None:
    at = state(as_of=BEFORE_DECEMBER, language=Language.DE)
    decision = outcome(answer(UNDRESSING_APP), at).step.decision
    assert decision.startswith("Keine verbotene Praxis nach Art. 5 trifft zu.")
    assert "Art. 5 Abs. 1 Buchst. ba gilt erst ab dem 2. Dezember 2026" in decision
    assert "am 16. November 2026" in decision


def test_an_open_december_practice_before_its_date_is_only_noted() -> None:
    unsure = UNDRESSING_APP.model_copy(update={"intimate_imagery": Answer.UNKNOWN})
    result = outcome(answer(unsure), state(as_of=BEFORE_DECEMBER))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert "it may apply" in result.step.decision
    assert result.follow_up_questions == ()


def test_a_december_point_the_text_read_lacks_is_left_out_of_the_citations() -> None:
    """Before 27 July 2026 the text has no point (ba): the date note still cites Art. 113(a)."""
    library = FakeLibrary(missing=frozenset({"art:5:1:ba", "art:5:1a:a:i"}))
    result = outcome(answer(UNDRESSING_APP), state(as_of=date(2026, 3, 1)), library)
    assert cited(result) == ["art:113:a"]


def test_a_missing_text_for_a_practice_in_force_is_an_error() -> None:
    library = FakeLibrary(missing=frozenset({"art:5:1:f"}))
    with pytest.raises(ProvisionNotFoundError):
        outcome(answer(WORKPLACE_EMOTIONS), library=library)


@pytest.mark.parametrize(
    ("facts", "extra"),
    [({"consent": Answer.YES}, []), ({"only_conceals": Answer.YES}, ["art:5:1b"])],
)
def test_consent_or_a_manipulation_that_shows_no_more_rules_out_point_ba(
    facts: dict[str, Answer], extra: list[str]
) -> None:
    """own-c-04 (consent) and own-c-06 (Art. 5(1b): a blur is not manipulation)."""
    given = UNDRESSING_APP.model_copy(update=facts)
    result = outcome(answer(given), state(as_of=AFTER_DECEMBER))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:5:1:ba", "art:5:1a:a:i", *extra, "art:113:a"]


def test_a_deployers_own_use_for_that_purpose_is_prohibited_under_1a_b() -> None:
    user = part(
        SexualMaterialAnswer, intimate_imagery=Answer.YES, deployer_generation_purpose=Answer.YES
    )
    result = outcome(answer(user), state(as_of=AFTER_DECEMBER))
    assert result.matched
    assert "art:5:1a:b" in cited(result)


def test_safeguards_that_work_keep_a_general_image_tool_out_of_point_ba() -> None:
    """own-c-03: no Art. 5(1a) route is met, so the capability alone is not prohibited."""
    tool = part(SexualMaterialAnswer, intimate_imagery=Answer.YES)
    result = outcome(answer(tool), state(as_of=AFTER_DECEMBER))
    assert not result.matched
    assert result.step.status is Status.DECIDED


def test_child_abuse_material_foreseeable_without_safeguards_is_prohibited_under_bb() -> None:
    unfiltered = part(
        SexualMaterialAnswer,
        child_abuse_material=Answer.YES,
        foreseeable_without_safeguards=Answer.YES,
    )
    result = outcome(answer(unfiltered), state(as_of=AFTER_DECEMBER))
    assert result.matched
    assert cited(result) == ["art:5:1:bb", "art:5:1a:a:ii", "art:113:a"]


def test_child_abuse_material_before_2_december_2026_is_not_yet_prohibited() -> None:
    unfiltered = part(
        SexualMaterialAnswer,
        child_abuse_material=Answer.YES,
        foreseeable_without_safeguards=Answer.YES,
    )
    result = outcome(answer(unfiltered), state(as_of=BEFORE_DECEMBER))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert "Art. 5(1)(bb) applies only from 2 December 2026" in result.step.decision
    assert "art:113:a" in cited(result)


def test_an_open_1a_route_is_asked() -> None:
    unsure = part(
        SexualMaterialAnswer, intimate_imagery=Answer.YES, generation_purpose=Answer.UNKNOWN
    )
    result = outcome(answer(unsure), state(as_of=AFTER_DECEMBER))
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "generation_purpose"


def test_the_original_text_has_no_point_ba() -> None:
    at = state(as_of=AFTER_DECEMBER, law_version=LawVersion.ORIGINAL)
    library = FakeLibrary()
    result = outcome(answer(UNDRESSING_APP), at, library)
    assert not result.matched
    assert cited(result) == ["art:5:1"]
    assert all(lookup.as_of is None for _, lookup in library.lookups)


# --- Point (h): real-time remote biometric identification -------------------------------------


def test_a_law_enforcement_use_meeting_every_condition_is_permitted_and_notified() -> None:
    """C7's follow-up: the exception and its conditions take a 5(1)(h) use out of the ban."""
    result = outcome(answer(part(RemoteIdentificationAnswer, **POLICE_LIVE_SEARCH)))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert cited(result) == [
        "art:5:1:h",
        "art:5:1:h:i",
        "art:5:2",
        "art:5:3",
        "art:5:5",
        "art:5:4",
    ]
    assert "(Art. 5(4))" in result.step.decision


@pytest.mark.parametrize(
    "unmet",
    [
        {"objective": RbiObjective.NONE},
        {"national_law_authorisation": Answer.NO},
        {"prior_authorisation": Answer.NO},
        {"targeted_use": Answer.NO},
        {"impact_assessment_registration": Answer.NO},
    ],
)
def test_a_law_enforcement_use_missing_a_condition_is_prohibited(unmet: dict[str, object]) -> None:
    result = outcome(answer(part(RemoteIdentificationAnswer, **{**POLICE_LIVE_SEARCH, **unmet})))
    assert result.matched
    assert result.step.status is Status.DECIDED
    assert "art:5:4" not in cited(result)


def test_an_open_authorisation_is_asked_with_prohibited_assumed() -> None:
    unsure = {**POLICE_LIVE_SEARCH, "prior_authorisation": Answer.UNKNOWN}
    result = outcome(answer(part(RemoteIdentificationAnswer, **unsure)))
    assert result.matched
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == "prior_authorisation"
    assert result.step.missing_fact.about == "art:5:3"


def test_an_unknown_objective_is_asked_with_prohibited_assumed() -> None:
    unsure = {**POLICE_LIVE_SEARCH, "objective": RbiObjective.UNKNOWN}
    result = outcome(answer(part(RemoteIdentificationAnswer, **unsure)))
    assert result.matched
    assert result.step.status is Status.NEEDS_MORE_INFORMATION
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.id == texts.RBI_OBJECTIVE.id


def test_a_private_operators_live_identification_is_not_law_enforcement() -> None:
    """own-c-17: Art. 5(1)(h) covers only law enforcement."""
    shop = part(RemoteIdentificationAnswer, real_time_identification=Answer.YES)
    result = outcome(answer(shop))
    assert not result.matched
    assert result.step.status is Status.DECIDED
    assert cited(result) == ["art:5:1:h"]


# --- Facts and guidance ------------------------------------------------------------------------


def test_the_answers_facts_and_guidance_are_cited() -> None:
    stated = Fact(
        text="Agents' calls are scored for mood.",
        evidence=EvidenceTag.STATED,
        source_span=SourceSpan(start=0, end=5),
    )
    emotions = WORKPLACE_EMOTIONS.model_copy(
        update={"evidence": EvidenceTag.STATED, "fact_numbers": (1,)}
    )
    result = outcome(answer(emotions, guidance=(2, 7)), state(facts=(stated,)))
    assert result.step.facts_used == (stated,)
    assert cited(result) == ["art:5:1:f", GUIDE_HITS[1]]


def test_english_guidance_for_a_german_case_is_marked_english_only() -> None:
    result = outcome(answer(WORKPLACE_EMOTIONS, guidance=(1,)), state(language=Language.DE))
    guidance = result.step.citations[-1]
    assert guidance.provision_id == GUIDE_HITS[0]
    assert guidance.english_only


def test_german_questions_are_asked_in_german() -> None:
    monitoring = part(
        EmotionAnswer, infers_emotions=Answer.UNKNOWN, workplace_or_education=Answer.YES
    )
    result = outcome(answer(monitoring), state(language=Language.DE))
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.text.startswith("Erkennt das System Gefühle")


# --- Retrieval ----------------------------------------------------------------------------------


def test_art_5_is_always_fetched_and_the_exclusions_reach_every_search() -> None:
    library = FakeLibrary()
    found = retrieve(state(language=Language.DE, exclude=EXCLUDED), library, node.SOURCE.article)
    assert found.article.provision_id == "art:5"
    assert library.lookups == [("art:5", Lookup(Language.DE, LawVersion.AMENDED, AS_OF, EXCLUDED))]
    assert [language for *_, language in library.searches] == [Language.DE, Language.EN]
    for _, lookup, _ in library.searches:
        assert lookup.exclude_source_example_ids == EXCLUDED
    assert [h.provision_id for h in found.guidance] == list(GUIDE_HITS)


def test_german_guidance_found_in_german_is_not_searched_again() -> None:
    library = FakeLibrary(guidance={Language.DE: GUIDE_HITS[:1]})
    found = retrieve(state(language=Language.DE), library, node.SOURCE.article)
    assert len(library.searches) == 1
    assert found.guidance[0].language is Language.DE


class FakeEmbedder:
    model = "fake"
    dimensions = 3

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0, 1.0]


def test_the_corpus_limits_the_search_to_its_guideline_without_a_cut_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, object]] = []

    def spy(
        query: str, language: Language, law_version: LawVersion, as_of: date, **kwargs: object
    ) -> SearchResults:
        seen.append(kwargs)
        return SearchResults(
            query=query,
            language=language,
            law_version=law_version,
            as_of=as_of,
            hits=(),
            max_distance=None,
            found=False,
            disclaimer=DISCLAIMER[language],
        )

    monkeypatch.setattr(retrieval, "search_ai_act", spy)
    connection, embedder = cast(psycopg.Connection, object()), FakeEmbedder()
    lookup = Lookup(Language.EN, LawVersion.AMENDED, AS_OF, EXCLUDED)
    corpus = GuidelineCorpus(connection, embedder, node.SOURCE)
    corpus.guidance("query", lookup, language=Language.EN)
    assert node.SOURCE.article == "art:5"
    assert frozenset({"guide-prohibited"}) == node.SOURCE.doc_keys
    assert node.SOURCE.passages == 6
    assert seen == [
        {
            "doc_keys": node.SOURCE.doc_keys,
            "exclude_source_example_ids": EXCLUDED,
            "include_held_out": False,
            "max_distance": None,
            "limit": node.SOURCE.passages,
            "embedder": embedder,
            "connection": connection,
        }
    ]


def test_provision_lookups_use_the_steps_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, ...]] = []

    def spy(
        provision_id: str, *args: object, connection: object, include_held_out: bool
    ) -> Provision:
        seen.append((provision_id, *args, connection))
        return provision(provision_id)

    monkeypatch.setattr(retrieval, "get_provision", spy)
    connection = cast(psycopg.Connection, object())
    library = GuidelineCorpus(connection, FakeEmbedder(), node.SOURCE)
    library.provision("art:5", Lookup(Language.DE, LawVersion.AMENDED, AS_OF, ()))
    assert seen == [("art:5", Language.DE, LawVersion.AMENDED, AS_OF, connection)]


# --- The model call -----------------------------------------------------------------------------


def _settings(**values: object) -> Settings:
    pinned = {"engine_model": LUNA, "engine_provider": LUNA_PROVIDER, **values}
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **pinned)  # pyright: ignore[reportCallIssue]


def _fake_chat(given: ProhibitedAnswer | str) -> GenericFakeChatModel:
    content = given if isinstance(given, str) else given.model_dump_json()
    return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))


def _retrieved() -> Retrieved:
    return retrieve(state(), FakeLibrary(), node.SOURCE.article)


def test_the_prompt_puts_instructions_and_art_5_first_and_the_description_last() -> None:
    messages = node.prohibited_messages(state(), _retrieved())
    assert messages[0].content == node.PROHIBITED_INSTRUCTIONS
    human = messages[1].content
    assert isinstance(human, str)
    assert human.startswith("The AI Act, Article 5 (amended text):\n\nText of art:5.")
    assert human.index("Text of art:5.") < human.index(f"1. [{GUIDE_HITS[0]}]")
    assert human.endswith(f"Description:\n{TOOL}")


def test_the_prompt_defaults_only_the_two_treatment_conditions() -> None:
    """Point (c)'s guidance (guidelines, paragraphs 163-167 and 175-177) defaults conditions (i)
    and (ii) to "no" when nothing points to them, never the base fact `social_scoring`, which
    keeps its own definition (E10, user 2026-10-06)."""
    section = node.PROHIBITED_INSTRUCTIONS.split("## social_scoring")[1].split("\n## ")[0]
    flat = " ".join(section.split())
    assert "paragraphs 163-167 and 175-177" in flat
    defaulted = flat.split('"no" (evidence "inferred"')[0].rsplit(". ", 1)[1].strip()
    assert defaulted == "Answer `unrelated_context_treatment` and `disproportionate_treatment`"
    assert "Answer `social_scoring` on its own definition" in flat


def test_the_prompt_leaves_dates_to_the_application() -> None:
    """The model never sees `as_of`, so the prefix stays the same for every date."""
    early = node.prohibited_messages(state(as_of=BEFORE_DECEMBER), _retrieved())
    late = node.prohibited_messages(state(as_of=AFTER_DECEMBER), _retrieved())
    assert early == late


def _run(check: ProhibitedCheck) -> EngineState:
    scripted = scripted_nodes(Script())
    checks = {**scripted.checks, StepName.PROHIBITED: check}
    graph = build_graph(
        EngineNodes(facts=scripted.facts, checks=checks, finalize=scripted.finalize)
    )
    given: EngineState = {
        "description": TOOL,
        "language": Language.EN,
        "law_version": LawVersion.AMENDED,
        "as_of": AS_OF,
        "exclude_source_example_ids": (),
    }
    return cast(EngineState, graph.invoke(given))


def test_a_decided_match_ends_the_run_as_prohibited() -> None:
    check = ProhibitedCheck(
        _settings(), chat=_fake_chat(answer(WORKPLACE_EMOTIONS)), library=FakeLibrary()
    )
    final = _run(check)
    assert [s.step for s in final.get("steps", ())] == [StepName.SCOPE, StepName.PROHIBITED]
    result = final.get("result")
    assert result is not None
    assert result.risk_class is RiskClass.PROHIBITED


def test_an_ambiguous_match_runs_every_check_with_prohibited_assumed() -> None:
    pressure = unsettled(part(ManipulationAnswer, manipulative_technique=Answer.YES))
    check = ProhibitedCheck(_settings(), chat=_fake_chat(answer(pressure)), library=FakeLibrary())
    final = _run(check)
    assert tuple(s.step for s in final.get("steps", ())) == STEP_ORDER
    result = final.get("result")
    assert result is not None
    assert result.risk_class is RiskClass.PROHIBITED
    assert result.status is Status.LEGALLY_AMBIGUOUS


REFUSAL_TEXT = "I'm sorry, but I cannot assist with that request."


def _filtered(content: str) -> GenericFakeChatModel:
    """A reply the provider's content filter stopped, as the recorded own-c-01 reply came back."""
    reply = AIMessage(content=content, response_metadata={"finish_reason": "content_filter"})
    return GenericFakeChatModel(messages=iter([reply]))


def test_a_provider_refusal_is_a_step_for_a_person_to_review() -> None:
    """Decision 029: not a broken output; prohibited assumed, Art. 5 cited, review asked."""
    check = ProhibitedCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=FakeLibrary())
    result = check(state(as_of=AFTER_DECEMBER))
    assert result.matched
    step = result.step
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.error == "provider_refusal"
    assert step.missing_fact is not None
    assert step.missing_fact.id == "person_review"
    assert result.follow_up_questions == (step.missing_fact,)
    assert cited(result) == ["art:5"]
    assert step.decision.startswith("The model provider's content filter blocked")
    assert "Art. 5(1)(ba) or (bb) may apply" in step.decision


def test_a_refusal_before_2_december_2026_says_ba_and_bb_do_not_apply_yet() -> None:
    """Any other Art. 5 point may still apply, so prohibited stays assumed; Art. 113(a) cited."""
    check = ProhibitedCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=FakeLibrary())
    result = check(state(as_of=BEFORE_DECEMBER))
    assert result.matched
    step = result.step
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert step.error == "provider_refusal"
    assert cited(result) == ["art:5", "art:113:a"]
    assert "Art. 5(1)(ba) and (bb) apply only from 2 December 2026" in step.decision
    assert "on 16 November 2026" in step.decision
    assert "the other prohibitions of Art. 5 can't be ruled out" in step.decision
    assert "may apply" not in step.decision


@pytest.mark.parametrize("as_of", [BEFORE_DECEMBER, AFTER_DECEMBER])
@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (Language.EN, "None of the Art. 5 prohibitions can be ruled out"),
        (Language.DE, "Keines der Verbote des Art. 5 lässt sich ausschließen"),
    ],
)
def test_a_refusal_under_the_original_text_names_no_point_ba_or_bb(
    as_of: date, language: Language, expected: str
) -> None:
    """The original text has no (ba) or (bb), and its Art. 113(a) doesn't name them."""
    check = ProhibitedCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=FakeLibrary())
    result = check(state(as_of=as_of, language=language, law_version=LawVersion.ORIGINAL))
    assert result.matched
    step = result.step
    assert step.status is Status.NEEDS_MORE_INFORMATION
    assert cited(result) == ["art:5"]
    assert expected in step.decision
    assert "ba" not in step.decision
    assert "113" not in step.decision


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (BEFORE_DECEMBER, "Art. 5 Abs. 1 Buchst. ba und bb gelten erst ab dem 2. Dezember 2026"),
        (AFTER_DECEMBER, "Art. 5 Abs. 1 Buchst. ba oder bb kann greifen"),
    ],
)
def test_a_refusal_is_reported_in_german(as_of: date, expected: str) -> None:
    check = ProhibitedCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=FakeLibrary())
    result = check(state(as_of=as_of, language=Language.DE))
    assert result.step.decision.startswith("Der Inhaltsfilter des Modellanbieters")
    assert expected in result.step.decision
    assert result.step.missing_fact is not None
    assert result.step.missing_fact.text.startswith("Bitte lassen Sie")


def test_a_refusal_keeps_the_run_going_with_prohibited_assumed() -> None:
    check = ProhibitedCheck(_settings(), chat=_filtered(REFUSAL_TEXT), library=FakeLibrary())
    final = _run(check)
    assert tuple(s.step for s in final.get("steps", ())) == STEP_ORDER
    result = final.get("result")
    assert result is not None
    assert result.risk_class is RiskClass.PROHIBITED


def test_a_filtered_reply_with_a_usable_answer_is_used() -> None:
    """own-c-16 came back as content_filter with a full answer: it is read as normal."""
    usable = answer(WORKPLACE_EMOTIONS).model_dump_json()
    check = ProhibitedCheck(_settings(), chat=_filtered(usable), library=FakeLibrary())
    result = check(state())
    assert result.step.status is Status.DECIDED
    assert result.step.error is None
    assert cited(result) == ["art:5:1:f"]


def test_a_reply_that_does_not_fit_the_schema_is_a_broken_output() -> None:
    reply = '{"manipulation": {"fact": "SECRET-VALUE-7731"}}'
    check = ProhibitedCheck(_settings(), chat=_fake_chat(reply), library=FakeLibrary())
    with pytest.raises(ProhibitedOutputError, match="doesn't fit the schema") as raised:
        check(state())
    assert "SECRET-VALUE-7731" not in str(raised.value)


def test_the_output_cap_leaves_room_for_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: dict[str, object] = {}

    def spy(**kwargs: object) -> BaseChatModel:
        asked.update(kwargs)
        return _fake_chat(answer())

    monkeypatch.setattr(node, "engine_chat_model", spy)
    ProhibitedCheck(_settings(), library=FakeLibrary())
    assert asked["max_tokens"] == 6000


def test_the_engine_model_must_be_pinned() -> None:
    with pytest.raises(LLMConfigError, match="ENGINE_PROVIDER"):
        ProhibitedCheck(_settings(engine_provider=None))


def _definitions() -> dict[str, dict[str, object]]:
    spec = node.PROHIBITED_RESPONSE_FORMAT["json_schema"]
    assert isinstance(spec, dict)
    return spec["schema"]["$defs"]


def test_the_response_format_requires_every_field() -> None:
    spec = node.PROHIBITED_RESPONSE_FORMAT["json_schema"]
    assert isinstance(spec, dict)
    assert spec["schema"]["required"] == list(ProhibitedAnswer.model_fields)
    for definition in _definitions().values():
        if "properties" in definition:
            assert definition["required"] == list(cast(dict[str, object], definition["properties"]))


def test_each_practice_answers_its_legal_openness_right_after_its_facts() -> None:
    """Strict structured output fills fields in order, so `settled_in_law` and `open_question`
    sit after each practice's key facts and before its summary."""
    practices = [
        field.annotation.__name__
        for name, field in ProhibitedAnswer.model_fields.items()
        if name != "guidance_numbers" and isinstance(field.annotation, type)
    ]
    for name in practices:
        fields = cast(list[str], _definitions()[name]["required"])
        at = fields.index("settled_in_law")
        assert fields[at : at + 2] == ["settled_in_law", "open_question"]
        assert fields[-3:] == ["evidence", "fact", "fact_numbers"]
        assert set(fields[at + 2 : -3]) <= {"open_on"}
        assert at >= 1


def test_follow_up_ids_do_not_collide_with_other_checks() -> None:
    """Finalize merges every check's questions by id, so an Art. 5 id must be its own."""
    from aiact.engine.nodes.high_risk_texts import ANNEX_I_QUESTIONS, PROFILING

    ours = [value.id for value in vars(texts).values() if hasattr(value, "question")]
    assert len(ours) == len(set(ours))
    theirs = {q.id for q in (*ANNEX_I_QUESTIONS, PROFILING)}
    assert not theirs & set(ours)


# --- The matcher ---------------------------------------------------------------------------------


def _case(**fields: object) -> BenchmarkCase:
    base: dict[str, object] = {
        "id": "own-c-90-invented",
        "set_name": "own",
        "language": "en",
        "description": TOOL,
        "label": {"risk_class": "prohibited", "role": "deployer"},
        "label_citation": ["art:5:1:f"],
        "tags": ["prohibition:art:5:1:f"],
    }
    return BenchmarkCase.model_validate({**base, **fields})


def test_the_matcher_needs_the_tagged_prohibition_cited() -> None:
    assert prohibited_matches(outcome(answer(WORKPLACE_EMOTIONS)), _case())
    scraping = part(FaceScrapingAnswer, untargeted_face_scraping=Answer.YES)
    assert not prohibited_matches(outcome(answer(scraping)), _case())


def test_the_matcher_needs_the_date_cited_for_a_prohibition_not_yet_applicable() -> None:
    case = _case(
        label={"risk_class": "limited_risk", "role": "provider"},
        tags=["trap:prohibition_not_yet_applicable"],
    )
    assert prohibited_matches(outcome(answer(UNDRESSING_APP), state(as_of=BEFORE_DECEMBER)), case)
    assert not prohibited_matches(outcome(answer()), case)


NOTES = "Open question: is the harm significant? Reading 1: prohibited. Reading 2: not."


def test_the_matcher_accepts_either_uncertain_status_for_unsettled_harm() -> None:
    """B12's rule: an unsettled significant harm may be flagged ambiguous or missing a fact."""
    case = _case(
        label={"risk_class": "prohibited", "status": "legally_ambiguous", "role": "deployer"},
        tags=["prohibition:art:5:1:a", "trap:significant_harm_unsettled"],
        notes=NOTES,
    )
    open_harm = part(
        ManipulationAnswer,
        manipulative_technique=Answer.YES,
        distorts_behaviour=Answer.YES,
        significant_harm=Answer.UNKNOWN,
    )
    asked = outcome(answer(open_harm))
    assert asked.step.status is Status.NEEDS_MORE_INFORMATION
    assert prohibited_matches(asked, case)
    assert prohibited_matches(outcome(answer(unsettled(open_harm))), case)
    decided = outcome(answer(open_harm.model_copy(update={"significant_harm": Answer.YES})))
    assert not prohibited_matches(decided, case)
    untagged = _case(
        label={"risk_class": "prohibited", "status": "legally_ambiguous", "role": "deployer"},
        tags=["prohibition:art:5:1:a"],
        notes=NOTES,
    )
    assert not prohibited_matches(asked, untagged)


# --- B5c replays: the own category-c cases, once their recordings exist -----------------------
#
# Record (live model and embedding calls, and the local corpus) with `RECORD_COMMAND`.

B5C_CASES_DIR = CASES_DIR / CaseSet.OWN.value / "c"
RECORD_COMMAND = "uv run pytest tests/engine/nodes/test_prohibited.py -k b5c --record-mode=once"


def _b5c_cases() -> list[BenchmarkCase]:
    paths = sorted(B5C_CASES_DIR.rglob("*.yaml")) if B5C_CASES_DIR.is_dir() else []
    return [case for path in paths for case in load_yaml_file(path)]


B5C_CASES = _b5c_cases()

REFUSED = KnownGap("provider content filter (decision 029)", refused)
REFUSED_IN_E10 = KnownGap("provider content filter (decision 029), E10 re-record", refused)

KNOWN_GAPS: dict[str, KnownGap] = {
    "own-c-01-undress-photo-app": REFUSED,
    "own-c-02-undress-app-before-december": REFUSED,
    "own-c-04-studio-digital-doubles-consent": REFUSED,
    "own-c-05-gossip-site-fake-nudes": REFUSED,
    "own-c-06-dating-app-nudity-blur": REFUSED_IN_E10,
    "own-c-07-unfiltered-image-generator": REFUSED,
    "own-c-14-kids-game-sad-pet-offers": REFUSED_IN_E10,
    "own-c-16-police-live-search-missing-child": REFUSED_IN_E10,
}
"""Recorded cases whose Art. 5 outcome differs from the label, with the reason; each fails when
it starts matching, so the entry is removed."""


def test_the_replays_include_a_case_on_each_side_of_2_december_2026() -> None:
    """The DoD's date pair: own-c-02 is dated before the December prohibitions, own-c-01 after."""
    dated = {case.id: case.as_of for case in B5C_CASES}
    before, after = (
        dated["own-c-02-undress-app-before-december"],
        dated["own-c-01-undress-photo-app"],
    )
    assert before is not None and before < DECEMBER_PROHIBITIONS_APPLY_FROM
    assert after is not None and after >= DECEMBER_PROHIBITIONS_APPLY_FROM
    assert replay_state(B5C_CASES[0], AS_OF)["as_of"] == B5C_CASES[0].as_of


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@contextmanager
def _live_corpus(settings: Settings) -> Iterator[GuidelineCorpus]:
    with connect() as connection:
        yield GuidelineCorpus(connection, OpenRouterEmbeddings(settings=settings), node.SOURCE)


@pytest.mark.vcr
@pytest.mark.parametrize(
    "case",
    B5C_CASES or [pytest.param(None, marks=pytest.mark.skip(reason="no B5c cases"))],
    ids=lambda case: case.id if isinstance(case, BenchmarkCase) else "no-cases",
)
def test_b5c_case_replay(
    case: BenchmarkCase,
    luna_settings: Settings,
    record_mode: str,
    vcr_cassette_dir: str,
    default_cassette_name: str,
) -> None:
    """Each B5c case's Art. 5 outcome against its label, at the case's own date (`as_of`)."""
    with corpus_recording(
        vcr_cassette_dir,
        default_cassette_name,
        record_mode,
        RECORD_COMMAND,
        lambda: _live_corpus(luna_settings),
    ) as recording:
        check = ProhibitedCheck(luna_settings, library=RecordedGuidelineLibrary(recording))
        run_state = replay_state(case, AS_OF)
        result = check(run_state)
    assert not unresolved_citations(result.step, run_state)
    matches = prohibited_matches(result, case)
    step = result.step
    shown = (result.matched, step.status, cited(result), step.decision)
    expect_known_gap(KNOWN_GAPS, result, case, matches=matches, shown=shown)
    assert matches, shown
