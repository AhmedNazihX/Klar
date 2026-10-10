"""The second-model label filter (B9): the blind prompt, the pinned call, the records and the
run. Descriptions here are invented, not benchmark cases."""

import json
from datetime import date
from pathlib import Path

import httpx
import openrouter
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.eval import label_filter
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.label_filter import (
    FilterAnswer,
    FilterRecord,
    LabelFilter,
    cases_to_label,
    filter_messages,
    input_sha256,
    law_context,
    read_records,
    run_filter,
)
from aiact.llm.routing import NO_RETRIES
from aiact.schemas import Language, RiskClass, Role, Status
from aiact.settings import Settings

HAIKU = "anthropic/claude-haiku-4.5"
EU_VERTEX = "google-vertex/europe"
RUN_DATE = date(2026, 10, 10)
LAW = "### Article 6 — test law"
DESCRIPTION = (
    "We are a 40-person staffing agency. We bought a tool that reads applicants' CVs and ranks "
    "them for each vacancy; recruiters only interview the top ten."
)


def make_case(number: int = 1, **changes: object) -> BenchmarkCase:
    values: dict[str, object] = {
        "id": f"own-z-{number:02d}-cv-ranker",
        "set_name": CaseSet.OWN,
        "language": Language.EN,
        "description": DESCRIPTION,
        "label": CaseLabel(
            risk_class=RiskClass.HIGH_RISK,
            status=Status.DECIDED,
            role=Role.DEPLOYER,
            annex_point=("annex:III:4:a",),
        ),
        "label_citation": ("annex:III:4:a",),
        "notes": "Label approved; the hidden note.",
        "tags": ("hidden-tag",),
    } | changes
    return BenchmarkCase.model_validate(values)


def answer(**changes: object) -> FilterAnswer:
    values: dict[str, object] = {
        "risk_class": RiskClass.HIGH_RISK,
        "status": Status.DECIDED,
        "role": Role.DEPLOYER,
        "annex_point": "annex:III:4:a",
        "reason": "Ranks job applicants: Annex III point 4(a) through Art. 6(2).",
    } | changes
    return FilterAnswer.model_validate(values)


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def _reply(content: str, cost: float | None = 0.004, **metadata: object) -> AIMessage:
    response_metadata: dict[str, object] = dict(metadata)
    if cost is not None:
        response_metadata["cost"] = cost
    return AIMessage(
        content=content,
        response_metadata=response_metadata,
        usage_metadata={"input_tokens": 13000, "output_tokens": 200, "total_tokens": 13200},
    )


def fake_filter(*replies: AIMessage) -> LabelFilter:
    return LabelFilter(_settings(), chat=GenericFakeChatModel(messages=iter(replies)), law=LAW)


class FailingChat(GenericFakeChatModel):
    def _generate(self, *args: object, **kwargs: object) -> object:  # pyright: ignore[reportIncompatibleMethodOverride]
        raise httpx.ConnectTimeout("no route")


# --- the prompt ----------------------------------------------------------------------------------


def test_filtered_sets_are_the_own_labelled_ones() -> None:
    assert tuple(s.value for s in label_filter.FILTERED_SETS) == (
        "commission_b",
        "own",
        "soft_pairs",
        "consistency",
        "annex_match",
    )


def test_the_prompt_never_shows_the_label_its_citation_notes_tags_or_source() -> None:
    case = make_case(
        source_example_id="hr-ex-999",
        label_citation=("art:26:7",),
        tags=("verdict:high", "hidden-tag"),
    )
    sent = json.dumps([m.model_dump() for m in filter_messages(case, LAW, RUN_DATE)])
    for hidden in ("hidden note", "hidden-tag", "verdict:high", "hr-ex-999", "art:26:7"):
        assert hidden not in sent, hidden
    assert DESCRIPTION in sent


def test_the_law_is_a_cached_prefix_and_the_case_comes_last() -> None:
    case = make_case(key_fact_answers={"human_review": "No, nobody checks the ranking."})
    system, human = filter_messages(case, LAW, RUN_DATE)
    assert system.content == [
        {
            "type": "text",
            "text": f"{label_filter.INSTRUCTIONS}\n## The AI Act (consolidated text)\n\n{LAW}",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert human.content == (
        f"Date: 2026-10-10\n\nDescription:\n{DESCRIPTION}\n\n"
        "Further answers from the company:\n- human_review: No, nobody checks the ranking."
    )


def test_a_case_with_its_own_date_is_judged_on_it() -> None:
    _, human = filter_messages(make_case(as_of=date(2026, 11, 30)), LAW, RUN_DATE)
    assert str(human.content).startswith("Date: 2026-11-30\n")


def test_the_input_hash_follows_what_is_sent_but_not_the_run_date() -> None:
    base = input_sha256(make_case())
    assert input_sha256(make_case(notes="Another note.", tags=())) == base
    assert input_sha256(make_case(description=DESCRIPTION + " More.")) != base
    assert input_sha256(make_case(key_fact_answers={"profiling": "Yes."})) != base
    assert input_sha256(make_case(as_of=date(2026, 12, 2))) != base


def test_law_context_quotes_the_amended_act_and_no_guideline() -> None:
    law = law_context()
    assert label_filter.LAW_PROVISIONS == (
        "art:2",
        "art:3:1",
        "art:3:3",
        "art:3:4",
        "art:3:6",
        "art:3:7",
        "art:5",
        "art:6",
        "art:25",
        "art:50",
        "art:111",
        "art:113",
        "annex:I",
        "annex:III",
    )
    assert label_filter.LAW_FILE == "ai-act-consolidated.en.jsonl"
    assert "### Article 6 — Classification rules for high-risk AI systems" in law
    assert "### Art. 3(4) (Article 3 — Definitions)" in law
    # Art. 6(1a) exists only in the amended text (the Digital Omnibus).
    assert "solely used for non-safety related aspects of user assistance" in law
    assert "hr-ex-" not in law


def test_law_context_names_a_provision_the_parsed_file_lacks(tmp_path: Path) -> None:
    row = {
        "provision_id": "art:2",
        "doc": "ai-act-consolidated",
        "language": "en",
        "kind": "article",
        "parent_id": None,
        "heading": "Article 2 — Scope",
        "text": "1. This Regulation applies to …",
        "amendment": None,
    }
    (tmp_path / label_filter.LAW_FILE).write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(LookupError, match="art:3:1, art:3:3"):
        law_context(tmp_path)


# --- one call ------------------------------------------------------------------------------------


def test_an_answer_becomes_a_record_with_its_cost() -> None:
    record = fake_filter(_reply(answer().model_dump_json())).label(make_case(), RUN_DATE)
    assert record.answer == answer()
    assert (record.error, record.cost_usd, record.tokens) == (None, 0.004, 13200)
    assert (record.model, record.provider) == (HAIKU, EU_VERTEX)
    assert record.judged_on == RUN_DATE
    assert record.input_sha256 == input_sha256(make_case())
    assert not record.is_cost_estimated


@pytest.mark.parametrize(
    "content", ["not json", json.dumps({"risk_class": "high_risk"}), json.dumps(DESCRIPTION)]
)
def test_a_broken_answer_is_a_failed_record_that_still_costs(content: str) -> None:
    record = fake_filter(_reply(content)).label(make_case(), RUN_DATE)
    assert record.answer is None
    assert record.error is not None and record.error.startswith("answer doesn't fit the schema")
    assert DESCRIPTION not in record.error
    assert (record.cost_usd, record.tokens) == (0.004, 13200)


def test_a_refused_call_is_recorded_as_a_refusal() -> None:
    refused = _reply("", finish_reason="content_filter")
    record = fake_filter(refused).label(make_case(), RUN_DATE)
    assert (record.answer, record.error) == (None, "refused by the provider's content filter")


def test_a_reply_without_a_cost_is_charged_the_estimate() -> None:
    record = fake_filter(_reply(answer().model_dump_json(), cost=None)).label(make_case(), RUN_DATE)
    assert record.answer == answer()
    assert (record.cost_usd, record.is_cost_estimated) == (0.02, True)


def test_a_failed_call_is_charged_the_estimate_and_named_by_type() -> None:
    labeller = LabelFilter(_settings(), chat=FailingChat(messages=iter(())), law=LAW)
    record = labeller.label(make_case(), RUN_DATE)
    assert (record.answer, record.error) == (None, "ConnectTimeout")
    assert (record.cost_usd, record.is_cost_estimated, record.tokens) == (0.02, True, 0)


def test_the_default_route_is_haiku_pinned_to_its_eu_endpoint_with_one_attempt() -> None:
    labeller = LabelFilter(_settings(), law=LAW)
    chat = labeller._chat  # pyright: ignore[reportPrivateUsage]
    assert chat.model_name == HAIKU  # pyright: ignore[reportAttributeAccessIssue]
    assert chat.openrouter_provider == {  # pyright: ignore[reportAttributeAccessIssue]
        "data_collection": "deny",
        "zdr": True,
        "order": [EU_VERTEX],
        "allow_fallbacks": False,
    }
    assert chat.max_retries == 0  # pyright: ignore[reportAttributeAccessIssue]
    assert chat.max_tokens == 1500  # pyright: ignore[reportAttributeAccessIssue]
    sdk_retries = chat.client.sdk_configuration.retry_config  # pyright: ignore[reportAttributeAccessIssue]
    assert sdk_retries is not None and sdk_retries.strategy == "none"


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
        "usage": {
            "prompt_tokens": 13000,
            "completion_tokens": 200,
            "total_tokens": 13200,
            "cost": 0.0041,
        },
    }


def test_the_request_carries_the_pin_the_schema_and_the_cache_breakpoint() -> None:
    """The real OpenRouter chat model over a mocked transport: what goes on the wire."""
    sent: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=_completion(answer().model_dump_json()))

    labeller = LabelFilter(_settings(), law=LAW)
    labeller._chat.client = openrouter.OpenRouter(  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]
        api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(handle)),
        retry_config=NO_RETRIES,
    )
    record = labeller.label(make_case(), RUN_DATE)
    assert record.answer == answer()
    assert (record.cost_usd, record.tokens) == (0.0041, 13200)
    body = sent[0]
    assert body["model"] == HAIKU
    assert body["provider"] == {
        "data_collection": "deny",
        "zdr": True,
        "order": [EU_VERTEX],
        "allow_fallbacks": False,
    }
    assert body["max_tokens"] == 1500
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    messages = body["messages"]
    assert isinstance(messages, list)
    assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert str(messages[-1]["content"]).endswith(DESCRIPTION)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="recording pending: the orchestrator records it after the reviews, then drops this mark",
)
@pytest.mark.vcr
def test_label_filter_roundtrip(openrouter_settings: Settings) -> None:
    """One real Haiku call on the pinned endpoint, with the real law text. Record with
    `uv run pytest tests/eval/test_label_filter.py -k roundtrip --record-mode=once`."""
    record = LabelFilter(openrouter_settings).label(make_case(), RUN_DATE)
    assert record.answer is not None, record.error
    assert record.answer.risk_class is RiskClass.HIGH_RISK
    assert record.cost_usd > 0 and not record.is_cost_estimated


# --- the run -------------------------------------------------------------------------------------


class CountingFilter(LabelFilter):
    """Answers every case, or fails every case, and remembers the order of the calls."""

    def __init__(self, *, is_failing: bool = False, cost: float = 0.004) -> None:
        self.model, self.provider, self.law = HAIKU, EU_VERTEX, LAW
        self.calls: list[str] = []
        self._is_failing, self._cost = is_failing, cost

    def label(self, case: BenchmarkCase, run_date: date) -> FilterRecord:
        self.calls.append(case.id)
        return FilterRecord(
            case_id=case.id,
            set_name=case.set_name,
            input_sha256=input_sha256(case),
            judged_on=run_date,
            model=self.model,
            provider=self.provider,
            answer=None if self._is_failing else answer(),
            error="ConnectTimeout" if self._is_failing else None,
            cost_usd=self._cost,
            tokens=100,
        )


CASES = tuple(make_case(n) for n in range(1, 8))


def test_the_run_appends_every_record_and_sums_the_cost(tmp_path: Path) -> None:
    answers = tmp_path / "answers.jsonl"
    summary = run_filter(
        CASES, CountingFilter(), run_date=RUN_DATE, concurrency=3, answers_file=answers
    )
    assert (summary.planned, summary.labelled, summary.failed) == (7, 7, 0)
    assert summary.cost_usd == pytest.approx(0.028)
    assert set(read_records(answers)) == {case.id for case in CASES}
    assert not summary.is_stopped_at_cap


def test_the_run_starts_no_batch_the_cap_cannot_cover(tmp_path: Path) -> None:
    labeller = CountingFilter(cost=0.02)
    # First batch: one call (0.02 <= 0.07); second: three (0.02 + 0.06 > 0.07), so it stops.
    summary = run_filter(
        CASES,
        labeller,
        run_date=RUN_DATE,
        max_cost_usd=0.07,
        concurrency=3,
        answers_file=tmp_path / "a.jsonl",
    )
    assert labeller.calls == [CASES[0].id]
    assert summary.is_stopped_at_cap
    assert summary.cost_usd == pytest.approx(0.02)


def test_a_batch_that_fails_entirely_stops_the_run(tmp_path: Path) -> None:
    labeller = CountingFilter(is_failing=True)
    summary = run_filter(
        CASES, labeller, run_date=RUN_DATE, concurrency=3, answers_file=tmp_path / "a.jsonl"
    )
    assert labeller.calls == [CASES[0].id]
    assert (summary.labelled, summary.failed, summary.cost_usd) == (0, 1, 0.004)


def test_only_new_edited_failed_or_rerouted_cases_are_labelled_again(tmp_path: Path) -> None:
    answers = tmp_path / "answers.jsonl"
    run_filter(CASES[:3], CountingFilter(), run_date=RUN_DATE, answers_file=answers)
    run_filter(CASES[3:4], CountingFilter(is_failing=True), run_date=RUN_DATE, answers_file=answers)
    records = read_records(answers)
    edited = make_case(2, description=DESCRIPTION + " Edited.")
    now = (CASES[0], edited, CASES[2], CASES[3], CASES[4])
    todo = cases_to_label(now, records, HAIKU, EU_VERTEX)
    assert [case.id for case in todo] == [edited.id, CASES[3].id, CASES[4].id]
    assert len(cases_to_label(now, records, "other/model", EU_VERTEX)) == len(now)


def test_a_missing_answers_file_has_no_records(tmp_path: Path) -> None:
    assert read_records(tmp_path / "none.jsonl") == {}
