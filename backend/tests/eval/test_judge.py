"""The judge (V4): Jev first, the backup LLM judge for unsure items. The claims here are invented,
not benchmark cases; the recorded round trips use a committed validation case."""

import json
from collections.abc import Callable

import httpx
import openrouter
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.eval import judge
from aiact.eval.judge import (
    CHECKS,
    BackupJudge,
    BackupVerdict,
    JevAnswer,
    JevJudge,
    Judge,
    JudgeCheck,
    JudgeError,
    JudgeItem,
    backup_messages,
    is_unsure,
    jev_state,
    needs_backup,
)
from aiact.eval.judge_validation import load_cases
from aiact.llm import DecisionsClient, DecisionsError, LLMConfigError
from aiact.llm.routing import NO_RETRIES
from aiact.schemas import Language
from aiact.settings import Settings

JEV = "typesafe/jev-1.13"
HAIKU = "anthropic/claude-haiku-5.5"
EU_VERTEX = "google-vertex/europe"
CLAIM = "Deployers must obtain each worker's written consent before using the system."
SOURCE = "Deployers who are employers shall inform workers' representatives and the workers."
ITEM = JudgeItem(
    check=JudgeCheck.CITATION_SUPPORT, language=Language.EN, claim=CLAIM, source=SOURCE
)
RECORDING_PENDING = pytest.mark.xfail(
    raises=CannotOverwriteExistingCassetteException,
    strict=True,
    reason="recording pending: the orchestrator records it after the reviews (V4)",
)


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


# --- the questions -------------------------------------------------------------------------------


def test_every_check_has_a_question_whose_yes_means_it_passes() -> None:
    assert set(CHECKS) == set(JudgeCheck)
    assert [check.value for check in JudgeCheck] == [
        "citation_support",
        "evidence_tag",
        "qa_support",
        "invented_content",
    ]
    for spec in CHECKS.values():
        assert spec.question.type == "noul"
        assert spec.question.instructions.endswith(".")


@pytest.mark.parametrize(
    ("check", "names"),
    [
        (JudgeCheck.CITATION_SUPPORT, ("claim", "cited_text")),
        (JudgeCheck.EVIDENCE_TAG, ("fact", "description")),
        (JudgeCheck.QA_SUPPORT, ("answer", "sources")),
        (JudgeCheck.INVENTED_CONTENT, ("document_text", "supplied_facts")),
    ],
)
def test_jev_reads_each_check_as_two_named_fields(
    check: JudgeCheck, names: tuple[str, str]
) -> None:
    item = ITEM.model_copy(update={"check": check})
    assert jev_state(item) == {names[0]: CLAIM, names[1]: SOURCE}


def test_an_item_is_capped_before_it_reaches_a_paid_judge() -> None:
    assert (judge.MAX_CLAIM_CHARS, judge.MAX_SOURCE_CHARS) == (4_000, 16_000)
    JudgeItem(check=ITEM.check, language=ITEM.language, claim="x" * 4_000, source="y" * 16_000)
    with pytest.raises(ValueError, match="at most 4000 characters"):
        JudgeItem(check=ITEM.check, language=ITEM.language, claim="x" * 4_001, source=SOURCE)
    with pytest.raises(ValueError, match="at most 16000 characters"):
        JudgeItem(check=ITEM.check, language=ITEM.language, claim=CLAIM, source="y" * 16_001)


def test_the_backup_judge_reads_the_same_question_with_the_item_last() -> None:
    system, human = backup_messages(ITEM)
    question = CHECKS[JudgeCheck.CITATION_SUPPORT].question
    assert question.instructions in system.text
    assert question.criteria.true in system.text and question.criteria.false in system.text
    assert CLAIM not in system.text
    assert human.text == f"claim:\n{CLAIM}\n\ncited_text:\n{SOURCE}"


# --- the unsure margin ---------------------------------------------------------------------------


def test_the_margin_and_the_yes_point_are_pinned() -> None:
    assert (judge.UNSURE_MARGIN, judge.YES_AT) == (0.3, 0.5)


@pytest.mark.parametrize(
    ("p_yes", "unsure"), [(0.5, True), (0.25, True), (0.75, True), (0.15, False), (0.85, False)]
)
def test_unsure_means_within_the_margin_of_one_half(p_yes: float, unsure: bool) -> None:
    assert is_unsure(p_yes, 0.3) is unsure


@pytest.mark.parametrize(("p_yes", "margin"), [(0.7, 0.2), (0.3, 0.2), (0.2, 0.3), (0.8, 0.3)])
def test_a_probability_on_the_edge_of_the_band_is_sure(p_yes: float, margin: float) -> None:
    assert not is_unsure(p_yes, margin)


def test_a_zero_margin_is_never_unsure_and_a_missing_answer_always_needs_the_backup() -> None:
    assert not is_unsure(0.5, 0.0)
    assert needs_backup(None, 0.0)
    assert not needs_backup(0.9, 0.3)


# --- the combined judge --------------------------------------------------------------------------


class FakeJev(JevJudge):
    def __init__(self, p_yes: float | None, cost: float = 0.00004) -> None:
        self.model = JEV
        self._p_yes, self._cost = p_yes, cost

    def ask(self, item: JudgeItem) -> JevAnswer:
        if self._p_yes is None:
            raise DecisionsError("decisions request failed with HTTP 503", self._cost, 0)
        return JevAnswer(self._p_yes, self._cost, 500)


class FakeBackup(BackupJudge):
    def __init__(self, holds: bool | None = True) -> None:
        self.model, self.provider = HAIKU, EU_VERTEX
        self._holds = holds
        self.calls = 0

    def ask(self, item: JudgeItem) -> BackupVerdict:
        self.calls += 1
        if self._holds is None:
            raise JudgeError("ConnectTimeout", 0.0006, 0)
        return BackupVerdict(self._holds, "The text says inform, not consent.", 0.0002, 900)


@pytest.mark.parametrize(("p_yes", "holds"), [(0.9, True), (0.1, False), (0.8, True)])
def test_a_sure_jev_decides_alone(p_yes: float, holds: bool) -> None:
    backup = FakeBackup()
    verdict = Judge(FakeJev(p_yes), backup).judge(ITEM)
    assert (verdict.holds, verdict.decided_by, verdict.p_yes) == (holds, "jev", p_yes)
    assert (verdict.reason, verdict.cost_usd, verdict.tokens) == (None, 0.00004, 500)
    assert backup.calls == 0


def test_an_unsure_jev_hands_over_to_the_backup_judge_and_both_costs_count() -> None:
    backup = FakeBackup(holds=False)
    verdict = Judge(FakeJev(0.6), backup).judge(ITEM)
    assert (verdict.holds, verdict.decided_by, verdict.p_yes) == (False, "backup", 0.6)
    assert verdict.reason == "The text says inform, not consent."
    assert verdict.cost_usd == pytest.approx(0.00024)
    assert verdict.tokens == 1400
    assert backup.calls == 1


def test_a_failed_jev_hands_over_to_the_backup_judge_keeping_its_cost() -> None:
    verdict = Judge(FakeJev(None, cost=0.00003), FakeBackup(holds=True)).judge(ITEM)
    assert (verdict.holds, verdict.decided_by, verdict.p_yes) == (True, "backup", None)
    assert verdict.cost_usd == pytest.approx(0.00023)


def test_no_verdict_when_the_backup_judge_must_answer_and_fails() -> None:
    with pytest.raises(JudgeError, match="ConnectTimeout") as caught:
        Judge(FakeJev(0.5), FakeBackup(holds=None)).judge(ITEM)
    assert caught.value.cost_usd == pytest.approx(0.00064)
    assert CLAIM not in str(caught.value)


def test_the_margin_given_decides_who_answers() -> None:
    backup = FakeBackup(holds=False)
    verdict = Judge(FakeJev(0.6), backup, margin=0.05).judge(ITEM)
    assert (verdict.decided_by, verdict.holds, backup.calls) == ("jev", True, 0)


# --- Jev on the wire -----------------------------------------------------------------------------


def test_jev_asks_the_check_as_one_noul_question_with_named_fields() -> None:
    sent: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        body = {
            "model": "typesafe/jev-1.13-20260917",
            "answers": {"holds": {"type": "noul", "noul": 0.07}},
            "usage": {"input_tokens": 300, "output_tokens": 3, "cost": 0.0000126},
        }
        return httpx.Response(200, json=body)

    settings = _settings()
    client = DecisionsClient(
        settings.judge_model,
        settings=settings,
        http=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    answer = JevJudge(settings, client=client).ask(ITEM)
    assert (answer.p_yes, answer.cost_usd, answer.tokens) == (0.07, 0.0000126, 303)
    assert sent[0]["model"] == JEV
    assert sent[0]["state"] == {"claim": CLAIM, "cited_text": SOURCE}
    question = sent[0]["questions"]
    assert isinstance(question, dict) and list(question) == ["holds"]
    assert question["holds"]["type"] == "noul"
    assert sent[0]["provider"] == {"data_collection": "deny", "zdr": True}


def test_the_jev_router_is_refused_as_the_judge() -> None:
    with pytest.raises(LLMConfigError, match="must not be typesafe/jev-router"):
        JevJudge(_settings(judge_model="typesafe/jev-router"))


# --- the backup judge ----------------------------------------------------------------------------


def _reply(content: str, cost: float | None = 0.0002, **metadata: object) -> AIMessage:
    response_metadata: dict[str, object] = dict(metadata)
    if cost is not None:
        response_metadata["cost"] = cost
    return AIMessage(
        content=content,
        response_metadata=response_metadata,
        usage_metadata={"input_tokens": 800, "output_tokens": 60, "total_tokens": 860},
    )


def _backup(*replies: AIMessage) -> BackupJudge:
    return BackupJudge(_settings(), chat=GenericFakeChatModel(messages=iter(replies)))


class FailingChat(GenericFakeChatModel):
    def _generate(self, *args: object, **kwargs: object) -> object:  # pyright: ignore[reportIncompatibleMethodOverride]
        raise httpx.ConnectTimeout("no route")


def test_the_backup_verdict_carries_its_reason_and_cost() -> None:
    reply = _reply(json.dumps({"holds": False, "reason": "Inform is not consent."}))
    verdict = _backup(reply).ask(ITEM)
    assert verdict == BackupVerdict(False, "Inform is not consent.", 0.0002, 860)


@pytest.mark.parametrize("content", ["not json", json.dumps({"holds": "maybe"}), json.dumps(CLAIM)])
def test_a_broken_backup_answer_is_an_error_that_still_costs(content: str) -> None:
    with pytest.raises(JudgeError, match="answer doesn't fit the schema") as caught:
        _backup(_reply(content)).ask(ITEM)
    assert (caught.value.cost_usd, caught.value.tokens) == (0.0002, 860)
    assert CLAIM not in str(caught.value)


def test_a_refused_backup_call_is_named_as_a_refusal() -> None:
    with pytest.raises(JudgeError, match="refused by the provider's content filter"):
        _backup(_reply("", finish_reason="content_filter")).ask(ITEM)


def test_a_failed_backup_call_is_charged_the_estimate_and_named_by_type() -> None:
    judge_ = BackupJudge(_settings(), chat=FailingChat(messages=iter(())))
    with pytest.raises(JudgeError, match=r"^ConnectTimeout$") as caught:
        judge_.ask(ITEM)
    assert caught.value.cost_usd == pytest.approx(0.00066)
    assert (caught.value.tokens, caught.value.is_cost_estimated) == (0, True)


def test_a_reply_without_a_cost_is_charged_the_estimate() -> None:
    reply = _reply(json.dumps({"holds": True, "reason": "It says so."}), cost=None)
    verdict = _backup(reply).ask(ITEM)
    assert (verdict.cost_usd, verdict.is_cost_estimated) == (pytest.approx(0.00066), True)


def test_the_call_estimates_are_pinned() -> None:
    assert (judge.PROMPT_TOKENS_BOUND, judge.MAX_OUTPUT_TOKENS) == (3_000, 600)
    assert pytest.approx(0.000126) == judge.JEV_CALL_ESTIMATE_USD
    assert pytest.approx(0.00066) == judge.BACKUP_CALL_ESTIMATE_USD


def test_the_default_route_is_haiku_5_5_pinned_to_its_eu_endpoint_with_one_attempt() -> None:
    backup = BackupJudge(_settings())
    chat = backup._chat  # pyright: ignore[reportPrivateUsage]
    assert (backup.model, backup.provider) == (HAIKU, EU_VERTEX)
    assert chat.model_name == HAIKU  # pyright: ignore[reportAttributeAccessIssue]
    assert chat.openrouter_provider == {  # pyright: ignore[reportAttributeAccessIssue]
        "data_collection": "deny",
        "zdr": True,
        "order": [EU_VERTEX],
        "allow_fallbacks": False,
    }
    assert chat.max_retries == 0  # pyright: ignore[reportAttributeAccessIssue]
    sdk_retries = chat.client.sdk_configuration.retry_config  # pyright: ignore[reportAttributeAccessIssue]
    assert sdk_retries is not None and sdk_retries.strategy == "none"


def test_the_production_judge_is_jev_then_the_pinned_backup() -> None:
    built = Judge.from_settings(_settings())
    assert built.margin == 0.3
    assert built._jev.model == JEV  # pyright: ignore[reportPrivateUsage]
    assert built._backup.model == HAIKU  # pyright: ignore[reportPrivateUsage]


def _completion(content: str) -> dict[str, object]:
    return {
        "id": "gen-test",
        "object": "chat.completion",
        "created": 1790000000,
        "model": HAIKU,
        "system_fingerprint": None,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": {"prompt_tokens": 800, "completion_tokens": 60, "total_tokens": 860, "cost": 2e-4},
    }


def test_the_backup_request_carries_the_pin_and_the_json_schema() -> None:
    """The real OpenRouter chat model over a mocked transport: what goes on the wire. Vertex
    rejects JSON mode for Claude, so the schema goes as `json_schema` (decision 005)."""
    sent: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=_completion(json.dumps({"holds": True, "reason": "Yes."})))

    backup = BackupJudge(_settings())
    backup._chat.client = openrouter.OpenRouter(  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]
        api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(handle)),
        retry_config=NO_RETRIES,
    )
    assert backup.ask(ITEM).holds is True
    body = sent[0]
    assert body["model"] == HAIKU
    assert body["provider"] == {
        "data_collection": "deny",
        "zdr": True,
        "order": [EU_VERTEX],
        "allow_fallbacks": False,
    }
    assert body["max_tokens"] == 600
    response_format = body["response_format"]
    assert isinstance(response_format, dict) and response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"]["required"] == ["holds", "reason"]


# --- recorded round trips ------------------------------------------------------------------------


def _committed_case() -> JudgeItem:
    """jv-en-02: a claim of written consent against Art. 26(7), which only asks to inform."""
    return next(case for case in load_cases() if case.id == "jv-en-02")


def _unwrapped[T](call: Callable[[], T]) -> T:
    """A missing recording surfaces as itself, not as the judge's error around it."""
    try:
        return call()
    except JudgeError as exc:
        if isinstance(exc.__cause__, CannotOverwriteExistingCassetteException):
            raise exc.__cause__ from None
        raise


@RECORDING_PENDING
@pytest.mark.vcr
def test_jev_judge_roundtrip(openrouter_settings: Settings) -> None:
    """Record with `uv run pytest tests/eval/test_judge.py -k roundtrip --record-mode=once`."""
    answer = JevJudge(openrouter_settings).ask(_committed_case())
    assert answer.p_yes < 0.5
    assert answer.cost_usd > 0


@RECORDING_PENDING
@pytest.mark.vcr
def test_backup_judge_roundtrip(openrouter_settings: Settings) -> None:
    """Haiku 5.5 on its pinned EU endpoint; needs the model allowed in the OpenRouter guardrail."""
    verdict = _unwrapped(lambda: BackupJudge(openrouter_settings).ask(_committed_case()))
    assert verdict.holds is False
    assert verdict.reason
    assert verdict.cost_usd > 0
