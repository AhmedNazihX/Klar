"""The V3 baselines: the answer-to-result mapping, both classifiers with fake and recorded model
responses, and a run through the V1 runner. Descriptions here are invented, not benchmark cases."""

import json

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.eval import baselines, runner
from aiact.eval.baselines import (
    JEV_MODEL,
    BaselineAnswer,
    BaselineOutputError,
    JevBaseline,
    LunaBaseline,
    to_result,
)
from aiact.eval.runner import (
    ClassifierFailedError,
    ClassifierInput,
    ClassifierUnavailableError,
    RunStatus,
    run_benchmark,
)
from aiact.llm import DecisionsClient, DecisionsError
from aiact.schemas import (
    DISCLAIMER,
    FollowUpQuestion,
    Language,
    OpenQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
)
from aiact.settings import Settings
from tests.eval.test_runner import CASES, SPLIT, MemoryStore, options

LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"
CV_RANKER = ClassifierInput(
    description=(
        "We are a 40-person staffing agency. We bought a tool that reads applicants' CVs and "
        "ranks them for each vacancy; recruiters only interview the top ten."
    ),
    language=Language.EN,
    exclude_source_example_ids=(),
)
USAGE = {"input_tokens": 400, "output_tokens": 60, "cost": 0.00002}


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def answer(**changes: object) -> BaselineAnswer:
    values: dict[str, object] = {
        "risk_class": RiskClass.HIGH_RISK,
        "status": Status.DECIDED,
        "role": Role.DEPLOYER,
        "annex_point": "annex:III:4:a",
        "transparency_duties": (),
        "reason": "Ranks job applicants (Annex III point 4(a)).",
        "missing_fact": None,
        "open_question": None,
    } | changes
    return BaselineAnswer.model_validate(values)


MISSING = FollowUpQuestion(id="human_review", text="Does a person review every ranking?")
OPEN = OpenQuestion(question="Is ranking profiling?", readings=("yes", "no"))


# --- answer to result ----------------------------------------------------------------------------


def test_high_risk_answer_runs_every_step_with_role_and_annex_point() -> None:
    result = to_result(answer(), Language.DE, "Test")

    assert [step.step for step in result.steps] == list(StepName)
    assert (result.risk_class, result.role, result.annex_point) == (
        RiskClass.HIGH_RISK,
        Role.DEPLOYER,
        "annex:III:4:a",
    )
    assert result.steps[2].decision.startswith("Test: high_risk. Ranks")
    assert result.steps[0].decision == "Test: not checked separately"
    assert result.disclaimer == DISCLAIMER[Language.DE]
    assert result.facts == ()


def test_out_of_scope_stops_at_scope_and_drops_what_does_not_apply() -> None:
    result = to_result(
        answer(risk_class=RiskClass.OUT_OF_SCOPE, transparency_duties=("art:50:1",)),
        Language.EN,
        "Test",
    )
    assert [step.step for step in result.steps] == [StepName.SCOPE]
    assert (result.role, result.annex_point, result.transparency_duties) == (None, None, ())


def test_decided_prohibited_stops_after_article_5() -> None:
    result = to_result(answer(risk_class=RiskClass.PROHIBITED), Language.EN, "Test")
    assert [step.step for step in result.steps] == [StepName.SCOPE, StepName.PROHIBITED]
    assert result.role is None


def test_ambiguous_prohibited_runs_on_with_the_open_question() -> None:
    result = to_result(
        answer(
            risk_class=RiskClass.PROHIBITED, status=Status.LEGALLY_AMBIGUOUS, open_question=OPEN
        ),
        Language.EN,
        "Test",
    )
    assert len(result.steps) == len(StepName)
    assert result.status is Status.LEGALLY_AMBIGUOUS
    assert result.steps[1].open_question == OPEN


def test_missing_fact_becomes_the_follow_up_question() -> None:
    result = to_result(
        answer(status=Status.NEEDS_MORE_INFORMATION, missing_fact=MISSING), Language.EN, "Test"
    )
    assert result.status is Status.NEEDS_MORE_INFORMATION
    assert result.follow_up_questions == (MISSING,)


def test_gap_fields_are_ignored_on_a_decided_answer() -> None:
    result = to_result(answer(missing_fact=MISSING, open_question=OPEN), Language.EN, "Test")
    assert result.status is Status.DECIDED
    assert result.follow_up_questions == ()


def test_limited_risk_lands_on_transparency_with_its_duties() -> None:
    result = to_result(
        answer(risk_class=RiskClass.LIMITED_RISK, transparency_duties=("art:50:1",)),
        Language.EN,
        "Test",
    )
    assert result.steps[3].decision.startswith("Test: limited_risk.")
    assert (result.annex_point, result.transparency_duties) == (None, ("art:50:1",))


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"risk_class": RiskClass.LIMITED_RISK}, "transparency_duties"),
        (
            {"risk_class": RiskClass.OUT_OF_SCOPE, "status": Status.NEEDS_MORE_INFORMATION},
            "needs_more_information step must set",
        ),
        ({"status": Status.LEGALLY_AMBIGUOUS}, "must set its open_question"),
    ],
)
def test_answers_that_break_the_contract_are_broken_outputs(
    changes: dict[str, object], problem: str
) -> None:
    with pytest.raises(BaselineOutputError, match=problem):
        to_result(answer(**changes), Language.EN, "Test")


# --- Luna baseline -------------------------------------------------------------------------------


def _fake_luna(content: str, cost: float = 0.0018) -> LunaBaseline:
    reply = AIMessage(
        content=content,
        response_metadata={"cost": cost},
        usage_metadata={"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500},
    )
    chat = GenericFakeChatModel(messages=iter([reply]))
    return LunaBaseline(_settings(engine_model=LUNA), chat=chat)


def test_luna_answer_becomes_a_result_with_its_cost() -> None:
    classified = _fake_luna(answer().model_dump_json()).classify(CV_RANKER)
    assert classified.result.risk_class is RiskClass.HIGH_RISK
    assert (classified.cost_usd, classified.tokens) == (0.0018, 1500)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"risk_class": "high_risk"}),
        answer(risk_class=RiskClass.LIMITED_RISK).model_dump_json(),
    ],
)
def test_broken_luna_output_fails_after_paying(content: str) -> None:
    with pytest.raises(ClassifierFailedError) as caught:
        _fake_luna(content).classify(CV_RANKER)
    assert (caught.value.cost_usd, caught.value.tokens) == (0.0018, 1500)
    assert isinstance(caught.value.cause, BaselineOutputError)
    assert CV_RANKER.description not in str(caught.value.cause)


def test_luna_is_pinned_to_the_engine_provider() -> None:
    luna = LunaBaseline(_settings(engine_model=LUNA, engine_provider=LUNA_PROVIDER))
    assert luna.info.model == LUNA
    assert luna._model.openrouter_provider == {  # pyright: ignore[reportAttributeAccessIssue]
        "data_collection": "deny",
        "zdr": True,
        "order": [LUNA_PROVIDER],
        "allow_fallbacks": False,
    }


def test_luna_prompt_puts_the_description_last() -> None:
    messages = baselines.luna_messages(CV_RANKER)
    assert messages[0].content == baselines.LUNA_INSTRUCTIONS
    assert str(messages[-1].content).endswith(CV_RANKER.description)


@pytest.fixture
def luna_settings(openrouter_settings: Settings) -> Settings:
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )


@pytest.mark.vcr
def test_luna_baseline_roundtrip(luna_settings: Settings) -> None:
    classified = LunaBaseline(luna_settings).classify(CV_RANKER)
    assert classified.result.risk_class is RiskClass.HIGH_RISK
    assert classified.cost_usd > 0
    assert classified.tokens > 0


# --- Jev baseline --------------------------------------------------------------------------------


def _jev(status: int, body: object) -> JevBaseline:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    http = httpx.Client(transport=httpx.MockTransport(handle))
    return JevBaseline(DecisionsClient(JEV_MODEL, settings=_settings(), http=http))


def _jev_body(risk_class: str, duty: str = "art_50_1") -> dict[str, object]:
    def choice(value: str) -> dict[str, object]:
        return {"type": "choice", "choice": value, "confidence": 0.8}

    answers = {
        "risk_class": choice(risk_class),
        "role": choice("provider"),
        "transparency_duty": choice(duty),
    }
    return {"model": JEV_MODEL, "answers": answers, "usage": USAGE}


def test_jev_choices_become_a_decided_result() -> None:
    classified = _jev(200, _jev_body("high_risk")).classify(CV_RANKER)
    result = classified.result
    assert (result.risk_class, result.status, result.role) == (
        RiskClass.HIGH_RISK,
        Status.DECIDED,
        Role.PROVIDER,
    )
    assert (result.annex_point, result.transparency_duties) == (None, ())
    assert "confidence 0.80" in result.steps[2].decision
    assert (classified.cost_usd, classified.tokens) == (0.00002, 460)


def test_jev_limited_risk_keeps_its_article_50_duty() -> None:
    result = _jev(200, _jev_body("limited_risk", "art_50_4")).classify(CV_RANKER).result
    assert result.transparency_duties == ("art:50:4",)


def test_jev_unusable_answer_fails_after_paying() -> None:
    with pytest.raises(ClassifierFailedError) as caught:
        _jev(200, _jev_body("unacceptable")).classify(CV_RANKER)
    assert caught.value.cost_usd == 0.00002


def test_jev_http_error_costs_nothing() -> None:
    with pytest.raises(DecisionsError):
        _jev(503, {"error": {"message": "down"}}).classify(CV_RANKER)


@pytest.mark.vcr
def test_jev_baseline_roundtrip(openrouter_settings: Settings) -> None:
    jev = JevBaseline(DecisionsClient(JEV_MODEL, settings=openrouter_settings))
    classified = jev.classify(CV_RANKER)
    assert classified.result.risk_class is RiskClass.HIGH_RISK
    assert classified.cost_usd > 0


# --- through the runner ---------------------------------------------------------------------------


def test_baselines_are_registered() -> None:
    assert {"baseline_luna", "baseline_jev"} <= runner.CLASSIFIERS.keys()


def test_unconfigured_luna_baseline_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(baselines, "get_settings", lambda: _settings())
    with pytest.raises(ClassifierUnavailableError, match="ENGINE_MODEL is not set"):
        runner.build_classifier("baseline_luna")


def test_jev_baseline_runs_a_five_case_subset_through_the_runner() -> None:
    store = MemoryStore()
    jev = _jev(200, _jev_body("high_risk"))
    summary = run_benchmark(
        CASES, jev, store, options(classifier_name="baseline_jev", subset=5), SPLIT
    )
    assert summary.status is RunStatus.COMPLETED
    assert (summary.cases_planned, summary.cases_scored, summary.cases_failed) == (5, 5, 0)
    assert summary.cost_usd == pytest.approx(5 * 0.00002)
    assert store.runs[summary.run_id]["config"]["model"] == JEV_MODEL  # pyright: ignore[reportIndexIssue]
