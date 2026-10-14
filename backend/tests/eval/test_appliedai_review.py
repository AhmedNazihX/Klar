"""The appliedAI disagreement review (aiact/eval/appliedai_review.py and its report, V9)."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from typer.testing import CliRunner, Result

from aiact.cli import app
from aiact.eval import appliedai_review_command, records
from aiact.eval.appliedai_review import (
    REVIEW_FILE,
    TITLE,
    VERDICT_MARK,
    NotAppliedAIRunError,
    Review,
    ReviewFormatError,
    Verdict,
    WrittenVerdict,
    build_review,
    parse_verdict,
    read_review_file,
    read_verdicts,
)
from aiact.eval.appliedai_review_report import (
    CREDIT,
    HOW_TO,
    engine_text,
    match_text,
    render_review,
)
from aiact.eval.cases import EVAL_DIR, AppliedAILabel, BenchmarkCase, CaseSet
from aiact.eval.metrics import Outcome, summarize
from aiact.eval.report import RunInfo, StoredCase
from aiact.schemas import ClassificationResult, Language, RiskClass, Status
from tests.eval.outcomes import refused_result, result
from tests.schemas.builders import rebuild

RUN_ID = UUID("00000000-0000-4000-8000-0000000000a1")
OTHER_RUN_ID = UUID("00000000-0000-4000-8000-0000000000a2")
DESCRIPTION = "Ein erfundenes System zur Bewerbervorauswahl."
COMMENT = "High risk, since it ranks applicants (made-up comment)"
HIGH, LOW, UNCLEAR = AppliedAILabel.HIGH, AppliedAILabel.LOW, AppliedAILabel.UNCLEAR
END = "## Annex I disagreements (1)\n"
NO_VERDICTS = "engine error 0, outdated label 0, label error 0, ambiguous 0"
LEFT_OUT = "Left out of the after column:"
OUTDATED_SAID = "outdated by later law (`outdated label`)"
WRONG_SAID = "wrong when made (`label error`)"


def info(benchmark: str = CaseSet.APPLIEDAI.value) -> RunInfo:
    return RunInfo(
        id=RUN_ID,
        benchmark=benchmark,
        git_sha="0" * 40,
        started_at=datetime(2026, 10, 14, tzinfo=UTC),
        model="openai/gpt-6-luna-20260922",
        classifier="engine",
        status="completed",
    )


def stored(
    case_id: str,
    label: AppliedAILabel,
    answer: ClassificationResult | None,
    *,
    function: str = "law",
    is_annex_i: bool = False,
    notes: str | None = None,
    is_scoring_error: bool = False,
) -> StoredCase:
    tags = (f"function:{function}", *(("annex_i",) if is_annex_i else ()))
    case = BenchmarkCase(
        id=case_id,
        set_name=CaseSet.APPLIEDAI,
        language=Language.DE,
        description=DESCRIPTION,
        label=label,
        notes=notes,
        tags=tags,
    )
    return StoredCase(outcome=Outcome(case=case, result=answer), is_scoring_error=is_scoring_error)


def run_cases() -> tuple[StoredCase, ...]:
    """One case per way a case can score; ids 002, 003, 005, 006 and 007 go to the review."""
    return (
        stored("aai-001", HIGH, result(), function="human_resource_management"),
        stored(
            "aai-002",
            HIGH,
            result(RiskClass.MINIMAL_RISK),
            function="human_resource_management",
            notes=COMMENT,
        ),
        stored("aai-003", LOW, result(RiskClass.OUT_OF_SCOPE)),  # matches, still reviewed
        stored("aai-004", UNCLEAR, result(status=Status.LEGALLY_AMBIGUOUS), is_annex_i=True),
        stored("aai-005", UNCLEAR, result(RiskClass.MINIMAL_RISK), is_annex_i=True),
        stored("aai-006", UNCLEAR, result(status=Status.NEEDS_MORE_INFORMATION)),  # separate
        stored("aai-007", LOW, None),  # failed
        stored("aai-008", UNCLEAR, refused_result()),  # not assessed: neither reviewed nor separate
        stored("aai-009", HIGH, result(), is_scoring_error=True),
    )


def review(verdicts: dict[str, WrittenVerdict] | None = None) -> Review:
    return build_review(info(), run_cases(), verdicts or {})


def written(text: str) -> WrittenVerdict:
    return WrittenVerdict(parse_verdict("x", text), text)


def with_verdicts(text: str, verdicts: dict[str, str]) -> str:
    """The rendered file with a verdict written after each named case's mark."""
    lines = text.splitlines()
    current = ""
    for index, line in enumerate(lines):
        if line.startswith("### Case "):
            current = line.removeprefix("### Case ")
        elif line.startswith(VERDICT_MARK) and current in verdicts:
            lines[index] = f"{VERDICT_MARK} {verdicts[current]}"
    return "\n".join(lines) + "\n"


# --- what goes to the review -------------------------------------------------------------------


def test_the_disagreements_are_the_cases_the_run_report_counts() -> None:
    drafted = review()
    ids = [case.case_id for case in drafted.disagreements]
    assert ids == ["aai-002", "aai-003", "aai-005", "aai-006", "aai-007"]
    scored = [case.outcome for case in run_cases() if not case.is_scoring_error]
    assert summarize(scored, None).appliedai_disagreement_review == len(ids)
    assert drafted.scoring_errors == ("aai-009",)
    assert drafted.missing == tuple(ids)


def test_a_run_of_another_set_is_refused() -> None:
    with pytest.raises(NotAppliedAIRunError, match="run of own, not appliedai"):
        build_review(info("own"), run_cases(), {})


def test_a_verdict_on_a_case_not_under_review_is_refused() -> None:
    with pytest.raises(ReviewFormatError, match="a verdict on aai-001, not a disagreement"):
        build_review(info(), run_cases(), {"aai-001": written("engine error")})


@pytest.mark.parametrize(
    ("case_id", "engine", "match"),
    [
        ("aai-001", "high_risk, decided, annex:III:4:a", "yes"),
        ("aai-002", "minimal_risk, decided", "no"),
        ("aai-003", "out_of_scope, decided", "yes"),
        ("aai-006", "high_risk, needs_more_information, annex:III:4:a", "counted separately"),
        ("aai-007", "failed (no result)", "no (failed)"),
        ("aai-008", "not assessed (prohibited refused)", "not assessed"),
    ],
)
def test_each_case_shows_the_engine_answer_and_the_match(
    case_id: str, engine: str, match: str
) -> None:
    case = next(case for case in review().cases if case.case_id == case_id)
    assert engine_text(case) == engine
    assert match_text(case) == match


# --- accuracy before and after the verdicts ----------------------------------------------------


def test_accuracy_before_the_verdicts_equals_the_run_report() -> None:
    lines = render_review(review()).splitlines()
    assert "| Every case | 50.0% (3/6) | 50.0% (3/6) |" in lines
    assert "| Without the Annex I cases | 50.0% (2/4) | 50.0% (2/4) |" in lines
    assert "| Annex I cases only | 50.0% (1/2) | 50.0% (1/2) |" in lines
    assert f"Verdicts: 0 of 5 disagreements ({NO_VERDICTS})." in lines
    assert f"{LEFT_OUT} 0 labels, 0 {OUTDATED_SAID} and 0 {WRONG_SAID}." in lines
    assert "The after column is provisional: 5 disagreements have no verdict yet." in lines
    assert "Counted separately (needs_more_information on an `unclear` case): 1." in lines


def test_cases_marked_outdated_label_leave_the_after_column_only() -> None:
    verdicts = {
        "aai-002": written("outdated label: Art. 6(3) exempts it"),
        "aai-003": written("ambiguous"),
        "aai-005": written("Outdated label"),
        "aai-006": written("engine error"),
        "aai-007": written("engine error"),
    }
    lines = render_review(review(verdicts)).splitlines()
    assert "| Every case | 50.0% (3/6) | 75.0% (3/4) |" in lines
    assert "| Without the Annex I cases | 50.0% (2/4) | 66.7% (2/3) |" in lines
    assert "| Annex I cases only | 50.0% (1/2) | 100.0% (1/1) |" in lines
    counts = (
        "Verdicts: 5 of 5 disagreements "
        "(engine error 2, outdated label 2, label error 0, ambiguous 1)."
    )
    assert counts in lines
    assert f"{LEFT_OUT} 2 labels, 2 {OUTDATED_SAID} and 0 {WRONG_SAID}." in lines
    assert not any(line.startswith("The after column is provisional") for line in lines)


def test_cases_marked_label_error_leave_the_after_column_too() -> None:
    verdicts = {
        "aai-002": written("label error: wrong even under the 2021 text"),
        "aai-005": written("Label Error"),
    }
    lines = render_review(review(verdicts)).splitlines()
    heading = "| Cases | Before excluding outdated and wrong labels "
    assert f"{heading}| After excluding outdated and wrong labels |" in lines
    assert "| Every case | 50.0% (3/6) | 75.0% (3/4) |" in lines
    assert "| Without the Annex I cases | 50.0% (2/4) | 66.7% (2/3) |" in lines
    assert "| Annex I cases only | 50.0% (1/2) | 100.0% (1/1) |" in lines


def test_label_errors_are_counted_apart_from_outdated_labels() -> None:
    verdicts = {
        "aai-002": written("outdated label"),
        "aai-003": written("ambiguous"),
        "aai-005": written("label error"),
        "aai-006": written("engine error"),
    }
    lines = render_review(review(verdicts)).splitlines()
    counts = (
        "Verdicts: 4 of 5 disagreements "
        "(engine error 1, outdated label 1, label error 1, ambiguous 1)."
    )
    assert counts in lines
    assert f"{LEFT_OUT} 2 labels, 1 {OUTDATED_SAID} and 1 {WRONG_SAID}." in lines
    row = "| aai-005 | law | unclear | minimal_risk, decided | no | yes | label error |"
    assert row in lines


def test_accuracy_per_appliedai_function() -> None:
    lines = render_review(review({"aai-002": written("outdated label")})).splitlines()
    assert "| human_resource_management | 2 | 1 | 50.0% (1/2) | 100.0% (1/1) |" in lines
    assert "| law | 6 | 4 | 50.0% (2/4) | 50.0% (2/4) |" in lines


def test_accuracy_per_appliedai_function_without_the_label_errors() -> None:
    verdicts = {"aai-002": written("label error"), "aai-005": written("label error")}
    lines = render_review(review(verdicts)).splitlines()
    heading = "| Function | Cases | Disagreements | Before excluding outdated and wrong labels "
    assert f"{heading}| After excluding outdated and wrong labels |" in lines
    assert "| human_resource_management | 2 | 1 | 50.0% (1/2) | 100.0% (1/1) |" in lines
    assert "| law | 6 | 4 | 50.0% (2/4) | 66.7% (2/3) |" in lines


# --- the file ------------------------------------------------------------------------------------


def test_annex_i_cases_are_listed_apart() -> None:
    text = render_review(review())
    others = text.split("## Cases (without Annex I)")[1].split("## Annex I cases")[0]
    annex_i = text.split("## Annex I cases (reported separately)")[1].split("## Disagreements")[0]
    assert "aai-004" not in others and "aai-005" not in others
    row = "| aai-004 | law | unclear | high_risk, legally_ambiguous, annex:III:4:a | yes |  |  |"
    assert row in annex_i.splitlines()
    assert "aai-001" not in annex_i
    general = text.split("## Disagreements (4)")[1].split("## Annex I disagreements")[0]
    assert "### Case aai-005" not in general
    annex_i_disagreements = text.split("## Annex I disagreements (1)")[1]
    assert annex_i_disagreements.count("### Case ") == 1
    assert "### Case aai-005" in annex_i_disagreements


def test_the_run_id_the_credit_and_the_quoted_comment() -> None:
    lines = render_review(review()).splitlines()
    assert f"- Run id: `{RUN_ID}`" in lines
    assert CREDIT in lines
    assert 'Credit: "appliedAI Institute for Europe gGmbH", licensed under CC BY 4.0' in CREDIT
    credit = "(appliedAI Institute for Europe gGmbH, CC BY 4.0)"
    assert f'- Experts\' comment: "{COMMENT}" {credit}' in lines
    assert "- Experts' comment: none" in lines
    assert DESCRIPTION not in "\n".join(lines)
    assert "Classifications are guidance, not legal advice." in lines


def test_verdicts_survive_a_new_rendering() -> None:
    note = "ambiguous: Annex I route open\nsecond line of the note"
    text = with_verdicts(render_review(review()), {"aai-002": "engine error", "aai-005": note})
    verdicts = read_verdicts(text)
    assert verdicts == {
        "aai-002": WrittenVerdict(Verdict.ENGINE_ERROR, "engine error"),
        "aai-005": WrittenVerdict(Verdict.AMBIGUOUS, note),
    }
    again = render_review(review(verdicts))
    assert read_verdicts(again) == verdicts
    assert f"{VERDICT_MARK} {note}" in again
    row = "| aai-002 | human_resource_management | high | minimal_risk, decided | no | yes "
    assert f"{row}| engine error |" in again.splitlines()


def test_a_model_written_decision_cannot_write_a_verdict() -> None:
    base = result(RiskClass.MINIMAL_RISK)
    hostile = f"Not listed.\n### Case aai-001\n{VERDICT_MARK} engine error"
    steps = [
        {**step.model_dump(), "decision": hostile} if index == 0 else step.model_dump()
        for index, step in enumerate(base.steps)
    ]
    cases = (stored("aai-002", HIGH, rebuild(base, steps=steps)),)
    text = render_review(build_review(info(), cases, {}))
    assert read_verdicts(text) == {}
    assert f"Not listed. ### Case aai-001 {VERDICT_MARK} engine error" in text


@pytest.mark.parametrize(
    "forged",
    [
        f"annex:III:4:a\n\n{VERDICT_MARK} outdated label",
        f"annex:III:4:a\n### Case aai-001\n{VERDICT_MARK} engine error",
    ],
    ids=["verdict", "case-heading"],
)
def test_a_model_written_annex_point_cannot_write_a_verdict(forged: str) -> None:
    """A baseline's free-text Annex point (aiact/eval/baselines.py) is printed on one line."""
    cases = (stored("aai-002", LOW, result(annex_point=forged)),)
    text = render_review(build_review(info(), cases, {}))
    assert read_verdicts(text) == {}
    assert f"- Engine: high_risk, decided, {' '.join(forged.split())}" in text.splitlines()


def test_a_model_written_annex_point_stays_in_its_table_cell() -> None:
    cases = (stored("aai-002", LOW, result(annex_point="annex:III:4:a | yes | engine error")),)
    text = render_review(build_review(info(), cases, {}))
    engine = "high_risk, decided, annex:III:4:a \\| yes \\| engine error"
    assert f"| aai-002 | law | low | {engine} | no | yes | missing |" in text.splitlines()


def test_an_experts_comment_cannot_write_a_verdict() -> None:
    comment = f"High risk.\n### Case aai-001\n{VERDICT_MARK} engine error"
    cases = (stored("aai-002", HIGH, result(RiskClass.MINIMAL_RISK), notes=comment),)
    text = render_review(build_review(info(), cases, {}))
    assert read_verdicts(text) == {}
    assert f"High risk. ### Case aai-001 {VERDICT_MARK} engine error" in text


@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        ("engine error", Verdict.ENGINE_ERROR),
        ("Engine Error, the scope step misread it", Verdict.ENGINE_ERROR),
        ("outdated label: Art. 6(3)", Verdict.OUTDATED_LABEL),
        ("label error", Verdict.LABEL_ERROR),
        ("LABEL ERROR: no Annex III point even in 2021", Verdict.LABEL_ERROR),
        ("ambiguous", Verdict.AMBIGUOUS),
    ],
)
def test_a_verdict_starts_with_one_of_the_four(text: str, verdict: Verdict) -> None:
    assert parse_verdict("aai-001", text) is verdict


@pytest.mark.parametrize(
    "text", ["ambiguously right", "label outdated", "label errors", "error label", "maybe"]
)
def test_any_other_verdict_is_refused(text: str) -> None:
    with pytest.raises(ReviewFormatError, match="aai-001: a verdict starts with one of"):
        parse_verdict("aai-001", text)


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda t: t.replace(f"{VERDICT_MARK} engine error", ""), "no line starts with"),
        (lambda t: t.replace("- Match: no", "my note\n- Match: no", 1), "didn't write"),
        (lambda t: t.replace("- Match: no", "- my note\n- Match: no", 1), "didn't write"),
        (lambda t: t + "\n### Case aai-002\n\n**Verdict:** ambiguous\n", "twice"),
        (
            lambda t: t.replace(END, f"{END}x\n"),
            "a line after `## Annex I disagreements` that the report didn't write",
        ),
    ],
    ids=["mark-removed", "line-before-mark", "list-line-before-mark", "listed-twice", "after-end"],
)
def test_an_edited_file_that_cannot_be_read_back_is_refused(
    edit: Callable[[str], str], message: str
) -> None:
    text = edit(with_verdicts(render_review(review()), {"aai-002": "engine error"}))
    with pytest.raises(ReviewFormatError, match=message):
        read_verdicts(text)


@pytest.mark.parametrize("heading", ["# Background", "## Background", "### Background"])
def test_a_note_line_starting_with_a_hash_is_refused_not_cut(heading: str) -> None:
    """A heading in a note would end the verdict, and a new rendering would drop the rest."""
    note = f"ambiguous: Annex I route open\n{heading}\nthe rest of the note"
    text = with_verdicts(render_review(review()), {"aai-002": note})
    with pytest.raises(ReviewFormatError, match=r"aai-002: .* a note line must not start with `#`"):
        read_verdicts(text)
    assert "a note line must not start with `#`" in HOW_TO


def test_the_review_is_written_to_the_story_output_by_default() -> None:
    assert REVIEW_FILE.relative_to(EVAL_DIR.parent).as_posix() == "eval/reports/appliedai_review.md"
    assert VERDICT_MARK == "**Verdict:**"
    values = [verdict.value for verdict in Verdict]
    assert values == ["engine error", "outdated label", "label error", "ambiguous"]
    assert "`label error` (the label didn't fit even the 2021 text" in HOW_TO


def test_a_file_written_with_the_three_first_verdicts_reads_back_unchanged() -> None:
    """A review drafted before `label error` existed: old headings, no left-out line."""
    new = render_review(review())
    old = new.replace("outdated and wrong labels", "outdated labels").splitlines()
    old_text = "\n".join(line for line in old if not line.startswith(LEFT_OUT))
    assert "outdated and wrong" not in old_text and LEFT_OUT not in old_text
    texts = {
        "aai-002": "engine error",
        "aai-003": "outdated label: Art. 6(3) exempts it",
        "aai-005": "ambiguous: Annex I route open\nsecond line of the note",
    }
    verdicts = read_verdicts(with_verdicts(old_text, texts))
    assert verdicts == {
        "aai-002": WrittenVerdict(Verdict.ENGINE_ERROR, texts["aai-002"]),
        "aai-003": WrittenVerdict(Verdict.OUTDATED_LABEL, texts["aai-003"]),
        "aai-005": WrittenVerdict(Verdict.AMBIGUOUS, texts["aai-005"]),
    }
    again = render_review(review(verdicts))
    assert read_verdicts(again) == verdicts
    for text in texts.values():
        assert f"{VERDICT_MARK} {text}" in again


def test_verdicts_of_another_run_are_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "appliedai_review.md"
    assert read_review_file(path, RUN_ID) == {}
    path.write_text(render_review(review()), encoding="utf-8")
    assert read_review_file(path, OTHER_RUN_ID) == {}  # no verdict yet: a new draft may replace it
    path.write_text(
        with_verdicts(render_review(review()), {"aai-002": "engine error"}), encoding="utf-8"
    )
    assert set(read_review_file(path, RUN_ID)) == {"aai-002"}
    with pytest.raises(ReviewFormatError, match=f"holds verdicts for run {RUN_ID}, not"):
        read_review_file(path, OTHER_RUN_ID)


# --- the command ---------------------------------------------------------------------------------

cli = CliRunner()


class Connection:
    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.fixture
def stored_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command reads `run_cases()` as the stored run, through the real file reading."""

    def load(conn: object, run_id: UUID, path: Path) -> Review:
        return build_review(info(), run_cases(), read_review_file(path, run_id))

    monkeypatch.setattr(records, "connect", Connection)
    monkeypatch.setattr(appliedai_review_command, "load_review", load)


def invoke(out: Path, *options: str) -> Result:
    return cli.invoke(
        app, ["evaluate", "appliedai-review", str(RUN_ID), "--out", str(out), *options]
    )


@pytest.mark.usefixtures("stored_run")
def test_the_command_drafts_then_checks_the_verdicts(tmp_path: Path) -> None:
    out = tmp_path / "reports" / "appliedai_review.md"
    drafted = invoke(out)
    assert drafted.exit_code == 0, drafted.output
    assert "8 cases, 5 disagreements (1 Annex I), 5 without a verdict." in drafted.stdout
    checked = invoke(out, "--check")
    assert checked.exit_code == 1
    assert "NO VERDICT: aai-002" in checked.stderr
    all_written = dict.fromkeys(review().missing, "engine error")
    out.write_text(with_verdicts(out.read_text(encoding="utf-8"), all_written), encoding="utf-8")
    before = out.read_text(encoding="utf-8")
    passed = invoke(out, "--check")
    assert passed.exit_code == 0, passed.output
    assert out.read_text(encoding="utf-8") == before  # --check writes nothing
    rendered = invoke(out)
    assert rendered.exit_code == 0
    assert "0 without a verdict" in rendered.stdout
    assert read_verdicts(out.read_text(encoding="utf-8")).keys() == all_written.keys()


@pytest.mark.usefixtures("stored_run")
def test_the_command_writes_nothing_over_an_unreadable_file(tmp_path: Path) -> None:
    out = tmp_path / "appliedai_review.md"
    broken = with_verdicts(render_review(review()), {"aai-002": "maybe"})
    out.write_text(broken, encoding="utf-8")
    outcome = invoke(out)
    assert outcome.exit_code == 2
    assert "aai-002: a verdict starts with one of" in outcome.stderr
    assert "Nothing was written." in outcome.stderr
    assert out.read_text(encoding="utf-8") == broken


@pytest.mark.usefixtures("stored_run")
def test_the_command_never_overwrites_a_file_that_is_not_a_review(tmp_path: Path) -> None:
    out = tmp_path / "notes.md"
    out.write_text("My own notes\n", encoding="utf-8")
    outcome = invoke(out)
    assert outcome.exit_code == 2
    assert f"{out} isn't an appliedAI review (its first line isn't `{TITLE}`)" in outcome.stderr
    assert out.read_text(encoding="utf-8") == "My own notes\n"
    assert invoke(out, "--check").exit_code == 2
    assert render_review(review()).splitlines()[0] == "# appliedAI disagreement review" == TITLE


def test_the_command_hides_the_database_error_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def connect() -> object:
        raise psycopg.OperationalError("no route to host db.internal.example")

    monkeypatch.setattr(records, "connect", connect)
    out = tmp_path / "appliedai_review.md"
    outcome = cli.invoke(app, ["evaluate", "appliedai-review", str(uuid4()), "--out", str(out)])
    assert outcome.exit_code == 2
    assert "Error: database error (OperationalError)" in outcome.stderr
    assert "db.internal.example" not in outcome.output
    assert not out.exists()
