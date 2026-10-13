"""Judged metrics (V5): the items each check sends, the tallies and the report section. Every
judge here is a fake: no test makes a model call."""

from collections.abc import Callable

import pytest

from aiact.drafting.draft import draft_document
from aiact.drafting.models import DraftDocument, Provenance
from aiact.drafting.prefill import DutyDateError
from aiact.eval import judged
from aiact.eval.judge import (
    UNSURE_MARGIN,
    BackupJudge,
    BackupVerdict,
    JevAnswer,
    JevJudge,
    Judge,
    JudgeCheck,
    JudgeError,
    JudgeItem,
    Verdict,
)
from aiact.eval.judged import (
    CheckScore,
    CodeCheck,
    JudgedRecordError,
    JudgedSettings,
    JudgeUnreachedError,
    citation_support_items,
    code_checked_documents,
    evidence_tag_items,
    is_judged,
    judge_one,
    judge_plan,
    parse_settings,
    planned_item,
    qa_answer,
    qa_support_item,
    read_stored,
    render_code_check,
    render_judged,
    run_totals,
    stored_scores,
)
from aiact.llm import DecisionsError
from aiact.schemas import EvidenceTag, Fact, Language, SourceSpan, StepName
from tests.schemas.builders import rebuild
from tests.schemas.worked_example import worked_example_result

DESCRIPTION = "A made-up description of a made-up tool."
EN = Language.EN


def _item(check: JudgeCheck = JudgeCheck.CITATION_SUPPORT, claim: str = "claim") -> JudgeItem:
    return JudgeItem(check=check, language=EN, claim=claim, source="source")


def _verdict(holds: bool, decided_by: str = "jev", cost: float = 0.0001) -> Verdict:
    return Verdict.model_validate(
        {
            "holds": holds,
            "decided_by": decided_by,
            "p_yes": 0.9 if holds else 0.1,
            "reason": None if decided_by == "jev" else "a reason",
            "cost_usd": cost,
            "tokens": 100,
        }
    )


class FakeJudges:
    """Answers each item with `answer(item)`: a verdict, or a JudgeError it raises."""

    def __init__(self, answer: Callable[[JudgeItem], Verdict | JudgeError]) -> None:
        self._answer = answer
        self.items: list[JudgeItem] = []

    def judge(self, item: JudgeItem) -> Verdict:
        self.items.append(item)
        answer = self._answer(item)
        if isinstance(answer, JudgeError):
            raise answer
        return answer


# --- the items -----------------------------------------------------------------------------------


def test_citation_support_sends_each_citing_step_with_its_quotes() -> None:
    result = worked_example_result()
    items = citation_support_items(result, EN)
    citing = [step for step in result.steps if step.citations]
    assert [item and item.claim for item in items] == [step.decision for step in citing]
    high_risk = next(item for item in items if item and item.claim.startswith("High-risk"))
    assert high_risk.check is JudgeCheck.CITATION_SUPPORT
    assert high_risk.source.startswith("Annex III 4(a)\nAI systems intended to be used for")


def test_a_step_without_citations_sends_nothing() -> None:
    result = worked_example_result()
    steps = [
        step.model_copy(update={"citations": ()}) if step.step is StepName.SCOPE else step
        for step in result.steps
    ]
    bare = rebuild(result, steps=[step.model_dump() for step in steps])
    assert len(citation_support_items(bare, EN)) == len(citation_support_items(result, EN)) - 1


def test_a_guidance_citation_keeps_its_id() -> None:
    citation = worked_example_result().steps[0].citations[0]
    guide = citation.model_copy(update={"provision_id": "guide:guide-prohibited:12"})
    assert judged.cited_text([guide]).startswith("guide:guide-prohibited:12\n")


def test_evidence_tags_send_each_distinct_stated_fact_against_the_description() -> None:
    items = evidence_tag_items(worked_example_result(), DESCRIPTION, EN)
    assert [item and item.claim for item in items] == [
        "The company uses a tool bought from a vendor",
        "The tool scores and ranks applicants",
        "The tool was not modified",
    ]
    assert all(item and item.source == DESCRIPTION for item in items)
    assert all(item and item.check is JudgeCheck.EVIDENCE_TAG for item in items)


def test_inferred_and_assumed_facts_are_not_judged_as_stated() -> None:
    stated = judged.stated_facts(worked_example_result())
    assert "The tool is used in the EU" not in stated  # assumed
    assert "No prohibited practice is described" not in stated  # inferred


def _stated(text: str) -> Fact:
    return Fact(text=text, evidence=EvidenceTag.STATED, source_span=SourceSpan(start=0, end=4))


def test_a_stated_fact_only_in_deciding_facts_or_a_step_is_sent_once() -> None:
    result = worked_example_result()
    deciding_only, step_only = _stated("Deciding only"), _stated("Step only")
    steps = [step.model_dump() for step in result.steps]
    steps[0]["facts_used"] = [
        *steps[0]["facts_used"],
        step_only.model_dump(),
        step_only.model_dump(),
    ]
    steps[1]["facts_used"] = [*steps[1]["facts_used"], deciding_only.model_dump()]
    extended = rebuild(
        result,
        deciding_facts=[
            *(f.model_dump() for f in result.deciding_facts),
            deciding_only.model_dump(),
        ],
        steps=steps,
    )
    assert deciding_only not in extended.facts and step_only not in extended.facts
    claims = [item and item.claim for item in evidence_tag_items(extended, DESCRIPTION, EN)]
    assert claims == [
        "The company uses a tool bought from a vendor",
        "The tool scores and ranks applicants",
        "The tool was not modified",
        "Deciding only",
        "Step only",
    ]


def test_qa_support_puts_question_and_answer_against_the_sources() -> None:
    item = qa_support_item("When?", "From 2 August 2026.", ["[art:113] Art. 113", "more"], EN)
    assert item is not None
    assert item.check is JudgeCheck.QA_SUPPORT
    assert item.claim == "Question: When?\nAnswer: From 2 August 2026."
    assert item.source == "[art:113] Art. 113\n\nmore"


def test_a_qa_answer_is_judged_only_when_drawn_from_the_sources() -> None:
    hits: list[object] = [{"doc_key": "ai-act", "provision_id": "art:113"}]
    answered = {"answer": "From 2 August 2026.", "answer_kind": "answered", "retrieved": hits}
    assert qa_answer(answered) == ("From 2 August 2026.", hits)
    assert qa_answer(answered | {"answer_kind": None}) is not None  # V6's stand-in answerer
    assert qa_answer(answered | {"answer_kind": "refused"}) is None
    assert qa_answer(answered | {"error": {"type": "X", "message": "y"}}) is None
    assert qa_answer(answered | {"answer": None}) is None
    assert qa_answer(None) is None


def test_an_answer_without_sources_cant_be_judged() -> None:
    assert qa_support_item("When?", "Never.", [], EN) is None


def test_an_item_over_the_judges_caps_isnt_sent() -> None:
    assert planned_item(JudgeCheck.EVIDENCE_TAG, EN, "x" * 4_001, "source") is None
    assert planned_item(JudgeCheck.EVIDENCE_TAG, EN, "x" * 4_000, "source") is not None
    assert planned_item(JudgeCheck.EVIDENCE_TAG, EN, "claim", "x" * 16_001) is None


# --- judging -------------------------------------------------------------------------------------


def test_a_verdict_counts_held_or_not_with_its_cost() -> None:
    assert judge_one(FakeJudges(lambda item: _verdict(True)), _item()) == CheckScore(
        held=1, judged=1, cost_usd=0.0001, tokens=100
    )
    assert judge_one(FakeJudges(lambda item: _verdict(False, "backup")), _item()) == CheckScore(
        held=0, judged=1, backup=1, cost_usd=0.0001, tokens=100
    )


def test_a_broken_reply_is_not_measured_with_what_it_spent() -> None:
    error = JudgeError("the reply didn't fit the schema", 0.0007, 300)
    score = judge_one(FakeJudges(lambda item: error), _item())
    assert score == CheckScore(not_measured=1, cost_usd=0.0007, tokens=300)
    assert score.rate.total == 0


def test_a_call_that_reached_no_model_is_raised_not_counted() -> None:
    error = JudgeError("ConnectTimeout", 0.0007, 300, is_call_failed=True)
    with pytest.raises(JudgeError) as raised:
        judge_one(FakeJudges(lambda item: error), _item())
    assert raised.value is error


def test_an_item_that_cant_be_sent_is_not_measured_and_costs_nothing() -> None:
    fake = FakeJudges(lambda item: _verdict(True))
    assert judge_one(fake, None) == CheckScore(not_measured=1)
    assert fake.items == []


class FakeJev(JevJudge):
    def __init__(self, p_yes: float | None) -> None:
        self.model = "typesafe/jev-1.13"
        self._p_yes = p_yes

    def ask(self, item: JudgeItem) -> JevAnswer:
        if self._p_yes is None:
            raise DecisionsError("decisions request failed with HTTP 503", 0.00004, 0)
        return JevAnswer(self._p_yes, 0.00004, 500)


class FailingBackup(BackupJudge):
    """The backup judge failing: a call that reached no model, or a broken reply."""

    def __init__(self, is_call_failed: bool = True) -> None:
        self.model, self.provider = "anthropic/claude-haiku-5.5", "google-vertex/europe"
        self._is_call_failed = is_call_failed

    def ask(self, item: JudgeItem) -> BackupVerdict:
        raise JudgeError(
            "ConnectTimeout" if self._is_call_failed else "ValidationError",
            0.0006,
            0,
            is_cost_estimated=self._is_call_failed,
            is_call_failed=self._is_call_failed,
        )


def test_the_real_judge_with_a_broken_backup_reply_is_not_measured_with_both_costs() -> None:
    judge = Judge(FakeJev(None), FailingBackup(is_call_failed=False), UNSURE_MARGIN)
    score = judge_one(judge, _item())
    assert score.not_measured == 1
    assert score.judged == 0
    assert score.cost_usd == pytest.approx(0.00064)


def test_the_real_judge_with_an_unreached_backup_raises_with_both_costs() -> None:
    judge = Judge(FakeJev(0.5), FailingBackup(), UNSURE_MARGIN)
    with pytest.raises(JudgeError) as raised:
        judge_one(judge, _item())
    assert raised.value.is_call_failed
    assert raised.value.cost_usd == pytest.approx(0.00064)


def test_a_sure_jev_answer_through_the_real_judge_is_a_verdict() -> None:
    score = judge_one(Judge(FakeJev(0.99), FailingBackup(), UNSURE_MARGIN), _item())
    assert score == CheckScore(held=1, judged=1, cost_usd=0.00004, tokens=500)


@pytest.mark.parametrize("concurrency", [1, 4])
def test_a_plan_is_tallied_per_check(concurrency: int) -> None:
    def answer(item: JudgeItem) -> Verdict | JudgeError:
        if item.claim == "fails":
            return JudgeError("the reply didn't fit the schema", 0.001, 10)
        return _verdict(item.claim == "holds")

    plan = {
        JudgeCheck.CITATION_SUPPORT: (_item(claim="holds"), _item(claim="no"), None),
        JudgeCheck.EVIDENCE_TAG: (_item(JudgeCheck.EVIDENCE_TAG, "fails"),),
        JudgeCheck.QA_SUPPORT: (),
    }
    scores = judge_plan(FakeJudges(answer), plan, concurrency)
    assert scores[JudgeCheck.CITATION_SUPPORT] == CheckScore(
        held=1, judged=2, not_measured=1, cost_usd=0.0002, tokens=200
    )
    assert scores[JudgeCheck.EVIDENCE_TAG] == CheckScore(not_measured=1, cost_usd=0.001, tokens=10)
    assert scores[JudgeCheck.QA_SUPPORT] == CheckScore()


def test_a_call_that_reached_no_model_stops_the_plan_with_what_it_spent() -> None:
    def answer(item: JudgeItem) -> Verdict | JudgeError:
        if item.claim == "unreached":
            return JudgeError("ConnectTimeout", 0.0006, 7, is_call_failed=True)
        return _verdict(True)

    fake = FakeJudges(answer)
    plan = {
        JudgeCheck.CITATION_SUPPORT: (_item(claim="holds"), _item(claim="unreached")),
        JudgeCheck.EVIDENCE_TAG: (_item(JudgeCheck.EVIDENCE_TAG, "after"),),
    }
    with pytest.raises(JudgeUnreachedError) as raised:
        judge_plan(fake, plan, concurrency=1)
    assert raised.value.cost_usd == pytest.approx(0.0007)
    assert raised.value.tokens == 107
    assert [item.claim for item in fake.items] == ["holds", "unreached"]  # none after it


# --- stored scores -------------------------------------------------------------------------------


def test_scores_are_stored_as_flat_numbers_and_read_back() -> None:
    scores = {JudgeCheck.CITATION_SUPPORT: CheckScore(held=2, judged=3, cost_usd=0.5, tokens=9)}
    stored = stored_scores(scores)
    assert stored == {
        "judged_citation_support_held": 2,
        "judged_citation_support_judged": 3,
        "judged_citation_support_not_measured": 0,
        "judged_citation_support_backup": 0,
        "judged_citation_support_cost_usd": 0.5,
        "judged_citation_support_tokens": 9,
    }
    assert read_stored({**stored, "risk_class_accuracy": True, "cost_usd": 1.0}) == scores
    assert is_judged(stored)
    assert not is_judged({"risk_class_accuracy": True, "cost_usd": 1.0})


def test_a_malformed_stored_score_is_an_error_naming_the_check() -> None:
    with pytest.raises(JudgedRecordError, match="evidence_tag"):
        read_stored({"judged_evidence_tag_held": -1})
    with pytest.raises(JudgedRecordError, match="evidence_tag"):
        read_stored({"judged_evidence_tag_judged": "three"})


def test_run_totals_sum_each_check_over_the_cases() -> None:
    a = {JudgeCheck.EVIDENCE_TAG: CheckScore(held=1, judged=1, cost_usd=0.1, tokens=1)}
    b = {
        JudgeCheck.EVIDENCE_TAG: CheckScore(judged=1, not_measured=1, cost_usd=0.2, tokens=2),
        JudgeCheck.CITATION_SUPPORT: CheckScore(held=1, judged=1),
    }
    totals = run_totals([a, b])
    evidence = totals[JudgeCheck.EVIDENCE_TAG]
    assert evidence.model_dump(exclude={"cost_usd"}) == {
        "held": 1,
        "judged": 2,
        "not_measured": 1,
        "backup": 0,
        "tokens": 3,
    }
    assert evidence.cost_usd == pytest.approx(0.3)
    assert totals[JudgeCheck.CITATION_SUPPORT] == CheckScore(held=1, judged=1)


# --- the settings and the report section ---------------------------------------------------------

SETTINGS = JudgedSettings(
    jev_model="typesafe/jev-1.13",
    backup_model="anthropic/claude-haiku-5.5",
    backup_provider="google-vertex/europe",
    margin=UNSURE_MARGIN,
)


def test_settings_are_read_from_the_runs_config() -> None:
    assert parse_settings({"judged": SETTINGS.model_dump(mode="json")}) == SETTINGS
    assert parse_settings({"model": "x"}) is None
    assert parse_settings({"judged": {"jev_model": "x"}}) is None
    assert parse_settings(None) is None


def test_the_section_shows_rates_what_wasnt_measured_and_the_cost() -> None:
    totals = {
        JudgeCheck.CITATION_SUPPORT: CheckScore(
            held=9, judged=10, not_measured=2, backup=1, cost_usd=0.0012, tokens=4000
        ),
        JudgeCheck.EVIDENCE_TAG: CheckScore(held=3, judged=4, cost_usd=0.0004, tokens=1000),
        JudgeCheck.QA_SUPPORT: CheckScore(held=1, judged=2, backup=2, cost_usd=0.0002),
    }
    lines = render_judged(totals, 5, 6, SETTINGS)
    assert lines[0] == "### Judged metrics"
    assert (
        "- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on "
        f"`google-vertex/europe`, unsure margin {UNSURE_MARGIN} (decision 006)"
    ) in lines
    assert "- Cases judged: 5 of 6" in lines
    assert "- Judge cost: $0.0018, 5000 tokens (not in the run's cost above)" in lines
    rows = [line for line in lines if line.startswith("| ")][2:]  # after the head and rule
    assert rows == [
        "| Citation support | 90.0% | 9/10 | 2 | 1 | $0.0012 | $0.000100 |",
        "| Evidence-tag accuracy | 75.0% | 3/4 | 0 | 0 | $0.0004 | $0.000100 |",
        "| Q&A support | 50.0% | 1/2 | 0 | 2 | $0.0002 | $0.000100 |",
    ]
    assert lines[-1].startswith("Not measured: ")


def test_a_check_with_nothing_judged_shows_na() -> None:
    lines = render_judged({JudgeCheck.QA_SUPPORT: CheckScore()}, 1, 1, None)
    assert "| Q&A support | n/a | 0/0 | 0 | 0 | $0.0000 | n/a |" in lines
    assert not any(line.startswith("- Judge: ") for line in lines)


def test_a_run_not_judged_says_so() -> None:
    assert render_judged({}, 0, 3, None) == [
        "Judged metrics: not judged yet (`aiact evaluate judged <run_id>`)."
    ]


def test_a_stored_invented_content_tally_is_not_read() -> None:
    stored = stored_scores({JudgeCheck.INVENTED_CONTENT: CheckScore(held=1, judged=1)})
    assert read_stored(stored) == {}


# --- no invented content, checked by code ------------------------------------------------------


def test_the_code_check_passes_every_drafted_document_of_a_result() -> None:
    result = worked_example_result()
    check = code_checked_documents([(result, EN), (result, Language.DE)])
    assert check == CodeCheck(passed=6, checked=6)
    assert render_code_check(check) == [
        "- No invented content: checked by code (P8a's `check_nothing_invented` on each document "
        "the results call for), not judged: 100.0%, 6/6 documents"
    ]


def test_a_document_with_an_added_sentence_fails_the_code_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def tampered(*args: object, **kwargs: object) -> DraftDocument:
        document = draft_document(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        sections = [
            section.model_copy(
                update={"paragraphs": (*section.paragraphs, "It is also certified.")}
            )
            if section.provenance is Provenance.CLASSIFICATION
            else section
            for section in document.sections
        ]
        return document.model_copy(update={"sections": tuple(sections)})

    monkeypatch.setattr(judged, "draft_document", tampered)
    assert code_checked_documents([(worked_example_result(), EN)]) == CodeCheck(0, 3)


def test_a_document_that_cant_be_drafted_isnt_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    def fails(*args: object, **kwargs: object) -> object:
        raise DutyDateError("two dates")

    monkeypatch.setattr(judged, "draft_document", fails)
    check = code_checked_documents([(worked_example_result(), EN)])
    assert check == CodeCheck(passed=0, checked=0, not_drafted=3)
    assert render_code_check(check)[0].endswith("n/a, 0/0 documents; 3 couldn't be drafted")
