"""The label-freeze check (B10a) against throwaway git repos: main holds the approved cases, a
story branch changes them, and the check compares the branch with its merge base."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import label_freeze
from aiact.eval.label_freeze import (
    FreezeCheckError,
    RecordKind,
    check_label_freeze,
)

LOG_HEADER = """# Label changes

| Date | Case id | Old → new | Reason | Approved by |
| --- | --- | --- | --- | --- |
| 2026-09-28 | own-b-01-old | minimal → limited | an older change | the user |
"""

CASE_B01 = """id: own-b-01-old
set_name: own
label:
  risk_class: minimal_risk
notes: first
"""

CASE_B02 = """id: own-b-02-second
set_name: own
label:
  risk_class: high_risk
"""

ACADEMIC = "".join(
    f"- id: academic-{number:04d}\n  label:\n    risk_class: minimal_risk\n"
    for number in range(1, 6)
)

OVERRIDES = """- id: academic-0001
  status: legally_ambiguous
  reason: open question
"""


def git(repo: Path, *arguments: str) -> str:
    settings = [
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
    ]
    completed = subprocess.run(
        ["git", *settings, *arguments], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def log_row(case_cell: str) -> str:
    return f"| 2026-09-30 | {case_cell} | old → new | a reason | the user |\n"


def append_log(repo: Path, *rows: str) -> None:
    path = repo / "eval/LABEL_CHANGES.md"
    path.write_text(path.read_text(encoding="utf-8") + "".join(rows), encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo whose main holds approved own/b and academic cases, on a fresh story branch."""
    git(tmp_path, "init", "-q", "-b", "main")
    write(tmp_path, "eval/LABEL_CHANGES.md", LOG_HEADER)
    write(tmp_path, "eval/cases/own/b/01-old.yaml", CASE_B01)
    write(tmp_path, "eval/cases/own/b/02-second.yaml", CASE_B02)
    write(tmp_path, "eval/cases/academic/minimal_risk.yaml", ACADEMIC)
    write(tmp_path, "eval/cases/academic_overrides.yaml", OVERRIDES)
    write(tmp_path, "eval/cases/academic/SOURCE.md", "source\n")
    commit_all(tmp_path, "approved cases")
    git(tmp_path, "checkout", "-q", "-b", "story/x")
    return tmp_path


def unlogged_ids(repo: Path) -> list[str]:
    return [case.key.case_id for case in check_label_freeze("main", repo).unlogged]


def relabel_academic(repo: Path, numbers: range) -> None:
    text = ACADEMIC
    for number in numbers:
        text = text.replace(
            f"academic-{number:04d}\n  label:\n    risk_class: minimal_risk",
            f"academic-{number:04d}\n  label:\n    risk_class: limited_risk",
        )
    write(repo, "eval/cases/academic/minimal_risk.yaml", text)


def tag_academic(repo: Path, numbers: range) -> None:
    """Add a tag to these academic cases: a change, but not a label change."""
    text = ACADEMIC
    for number in numbers:
        text = text.replace(
            f"academic-{number:04d}\n  label:",
            f"academic-{number:04d}\n  tags: [scoring:x]\n  label:",
        )
    write(repo, "eval/cases/academic/minimal_risk.yaml", text)


def test_an_unchanged_branch_passes(repo: Path) -> None:
    report = check_label_freeze("main", repo)
    assert report.is_ok
    assert report.changed == ()
    assert report.base_sha == git(repo, "rev-parse", "main").strip()


def test_a_changed_approved_case_without_an_entry_fails(repo: Path) -> None:
    write(repo, "eval/cases/own/b/01-old.yaml", CASE_B01.replace("minimal_risk", "high_risk"))
    commit_all(repo, "relabel")
    report = check_label_freeze("main", repo)
    assert not report.is_ok
    assert [case.describe() for case in report.unlogged] == [
        "case own-b-01-old (eval/cases/own/b/01-old.yaml) changed"
    ]


def test_a_changed_approved_case_with_a_new_entry_passes(repo: Path) -> None:
    write(repo, "eval/cases/own/b/01-old.yaml", CASE_B01.replace("minimal_risk", "high_risk"))
    append_log(repo, log_row("own-b-01-old"))
    commit_all(repo, "relabel, logged")
    report = check_label_freeze("main", repo)
    assert report.is_ok
    assert len(report.changed) == 1


def test_an_entry_on_the_base_doesnt_cover_a_new_change(repo: Path) -> None:
    """own-b-01-old already has a row on main; a second change needs a row of its own."""
    write(repo, "eval/cases/own/b/01-old.yaml", CASE_B01.replace("first", "second"))
    assert unlogged_ids(repo) == ["own-b-01-old"]


def test_notes_and_tags_count_as_changes(repo: Path) -> None:
    write(repo, "eval/cases/own/b/02-second.yaml", CASE_B02 + "tags: [scoring:x]\n")
    assert unlogged_ids(repo) == ["own-b-02-second"]


def test_uncommitted_edits_are_checked(repo: Path) -> None:
    write(repo, "eval/cases/own/b/02-second.yaml", CASE_B02.replace("high_risk", "prohibited"))
    assert unlogged_ids(repo) == ["own-b-02-second"]


def test_a_new_case_file_needs_no_entry(repo: Path) -> None:
    write(repo, "eval/cases/own/c/01-new.yaml", CASE_B02.replace("own-b-02", "own-c-01"))
    write(repo, "eval/cases/own/c/02-new.yaml", CASE_B02.replace("own-b-02", "own-c-02"))
    commit_all(repo, "new category")
    report = check_label_freeze("main", repo)
    assert report.is_ok
    assert report.changed == ()


def test_a_new_case_appended_to_an_approved_file_needs_no_entry(repo: Path) -> None:
    extra = "- id: academic-0099\n  label:\n    risk_class: high_risk\n"
    write(repo, "eval/cases/academic/minimal_risk.yaml", ACADEMIC + extra)
    assert check_label_freeze("main", repo).is_ok


def test_formatting_comments_and_moves_are_not_changes(repo: Path) -> None:
    reordered = "# a comment\nset_name: own\nid: own-b-02-second\nlabel: {risk_class: high_risk}\n"
    (repo / "eval/cases/own/b/02-second.yaml").unlink()
    write(repo, "eval/cases/own/b/renamed.yaml", reordered)
    assert check_label_freeze("main", repo).is_ok


def test_a_removed_approved_case_needs_an_entry(repo: Path) -> None:
    (repo / "eval/cases/own/b/02-second.yaml").unlink()
    report = check_label_freeze("main", repo)
    assert [case.describe() for case in report.unlogged] == [
        "case own-b-02-second (eval/cases/own/b/02-second.yaml) removed"
    ]


def test_a_changed_override_needs_an_entry_naming_its_case(repo: Path) -> None:
    write(repo, "eval/cases/academic_overrides.yaml", OVERRIDES.replace("open", "another"))
    report = check_label_freeze("main", repo)
    assert [(case.key.kind, case.key.case_id) for case in report.unlogged] == [
        (RecordKind.OVERRIDE, "academic-0001")
    ]
    append_log(repo, log_row("academic-0001"))
    assert check_label_freeze("main", repo).is_ok


def test_bare_numbers_reuse_the_prefix_of_the_id_before_them(repo: Path) -> None:
    relabel_academic(repo, range(1, 4))
    append_log(repo, log_row("academic-0001, 0002, `0003`"))
    assert check_label_freeze("main", repo).is_ok


def test_a_bulk_row_covers_exactly_its_count(repo: Path) -> None:
    tag_academic(repo, range(1, 4))
    append_log(repo, log_row("3 academic cases (by rule: source label minimal)"))
    report = check_label_freeze("main", repo)
    assert report.is_ok
    assert len(report.changed) == 3


@pytest.mark.parametrize("declared", [2, 4, 100])
def test_a_bulk_count_that_isnt_exact_fails(repo: Path, declared: int) -> None:
    tag_academic(repo, range(1, 4))
    append_log(repo, log_row(f"{declared} academic cases (by rule: source label minimal)"))
    report = check_label_freeze("main", repo)
    assert not report.is_ok
    assert [case.key.case_id for case in report.unlogged] == [
        f"academic-{number:04d}" for number in range(1, 4)
    ]
    assert report.bulk_mismatches == (
        f"bulk rows declare {declared} academic cases, but 3 changed academic cases "
        "(label changes aside) match no id row",
    )


def test_bulk_rows_for_one_prefix_are_summed(repo: Path) -> None:
    tag_academic(repo, range(1, 5))
    append_log(repo, log_row("1 academic cases (rule a)"), log_row("3 academic cases (rule b)"))
    assert check_label_freeze("main", repo).is_ok


def test_summed_bulk_rows_must_still_match_exactly(repo: Path) -> None:
    tag_academic(repo, range(1, 5))
    append_log(repo, log_row("1 academic cases (rule a)"), log_row("2 academic cases (rule b)"))
    report = check_label_freeze("main", repo)
    assert len(report.unlogged) == 4
    assert len(report.bulk_mismatches) == 1


def test_a_bulk_row_counts_only_cases_no_id_row_names(repo: Path) -> None:
    tag_academic(repo, range(1, 5))
    append_log(repo, log_row("academic-0004"), log_row("3 academic cases (by rule)"))
    assert check_label_freeze("main", repo).is_ok


def test_a_bulk_row_never_covers_a_label_change(repo: Path) -> None:
    """academic-0001's risk class flips among tag-only changes: only an id row covers it."""
    tag_academic(repo, range(2, 4))
    text = (repo / "eval/cases/academic/minimal_risk.yaml").read_text(encoding="utf-8")
    write(
        repo,
        "eval/cases/academic/minimal_risk.yaml",
        text.replace(
            "academic-0001\n  label:\n    risk_class: minimal_risk",
            "academic-0001\n  label:\n    risk_class: high_risk",
        ),
    )
    append_log(repo, log_row("2 academic cases (by rule)"))
    report = check_label_freeze("main", repo)
    assert [case.key.case_id for case in report.unlogged] == ["academic-0001"]
    assert report.bulk_mismatches == ()
    append_log(repo, log_row("academic-0001"))
    assert check_label_freeze("main", repo).is_ok


def test_an_as_of_edit_is_a_label_change(repo: Path) -> None:
    """The case date decides a date-dependent label, so only an id row covers an edit to it: the
    bulk row covers own-b-01's tag change but not own-b-02's new date."""
    write(repo, "eval/cases/own/b/01-old.yaml", CASE_B01 + "tags: [scoring:x]\n")
    write(repo, "eval/cases/own/b/02-second.yaml", CASE_B02 + "as_of: 2026-12-15\n")
    append_log(repo, log_row("1 own-b cases (by rule)"))
    report = check_label_freeze("main", repo)
    assert [case.key.case_id for case in report.unlogged] == ["own-b-02-second"]
    assert report.bulk_mismatches == ()
    append_log(repo, log_row("own-b-02-second"))
    assert check_label_freeze("main", repo).is_ok


def test_a_bulk_row_never_covers_an_override_status_change(repo: Path) -> None:
    write(
        repo,
        "eval/cases/academic_overrides.yaml",
        OVERRIDES.replace("legally_ambiguous", "decided"),
    )
    append_log(repo, log_row("1 academic cases (by rule)"))
    report = check_label_freeze("main", repo)
    assert [(case.key.kind, case.key.case_id) for case in report.unlogged] == [
        (RecordKind.OVERRIDE, "academic-0001")
    ]


def test_a_bulk_row_never_covers_a_removed_case(repo: Path) -> None:
    (repo / "eval/cases/own/b/02-second.yaml").unlink()
    append_log(repo, log_row("1 own cases (by rule)"))
    assert unlogged_ids(repo) == ["own-b-02-second"]


def test_a_bulk_row_covers_only_its_prefix(repo: Path) -> None:
    write(repo, "eval/cases/own/b/02-second.yaml", CASE_B02 + "tags: [scoring:x]\n")
    append_log(repo, log_row("1 academic cases (by rule)"))
    report = check_label_freeze("main", repo)
    assert [case.key.case_id for case in report.unlogged] == ["own-b-02-second"]
    assert len(report.bulk_mismatches) == 1


def test_a_bulk_prefix_can_name_a_category(repo: Path) -> None:
    write(repo, "eval/cases/own/b/02-second.yaml", CASE_B02 + "tags: [scoring:x]\n")
    append_log(repo, log_row("1 own-b cases (by rule)"))
    assert check_label_freeze("main", repo).is_ok


def test_realigned_log_columns_are_not_edits(repo: Path) -> None:
    old = "| 2026-09-28 | own-b-01-old | minimal → limited | an older change | the user |"
    realigned = "|  2026-09-28  |own-b-01-old|   minimal → limited | an older change |the user|"
    path = repo / "eval/LABEL_CHANGES.md"
    path.write_text(LOG_HEADER.replace(old, realigned), encoding="utf-8")
    assert check_label_freeze("main", repo).is_ok


def test_an_edited_old_log_row_fails(repo: Path) -> None:
    path = repo / "eval/LABEL_CHANGES.md"
    path.write_text(LOG_HEADER.replace("an older change", "rewritten"), encoding="utf-8")
    report = check_label_freeze("main", repo)
    assert not report.is_ok
    assert report.edited_log_rows == (
        "| 2026-09-28 | own-b-01-old | minimal → limited | an older change | the user |",
    )


def test_the_base_is_the_merge_base_not_the_tip_of_main(repo: Path) -> None:
    """Cases main gains or relabels after the branch left it aren't the branch's changes."""
    git(repo, "checkout", "-q", "main")
    write(repo, "eval/cases/own/b/02-second.yaml", CASE_B02.replace("high_risk", "prohibited"))
    write(repo, "eval/cases/own/d/01-later.yaml", CASE_B02.replace("own-b-02", "own-d-01"))
    append_log(repo, log_row("own-b-02-second"))
    commit_all(repo, "main moves on")
    git(repo, "checkout", "-q", "story/x")
    report = check_label_freeze("main", repo)
    assert report.is_ok
    assert report.base_sha != git(repo, "rev-parse", "main").strip()


def test_an_unknown_base_ref_is_an_error(repo: Path) -> None:
    with pytest.raises(FreezeCheckError, match="merge-base"):
        check_label_freeze("no-such-branch", repo)


def test_a_base_that_looks_like_an_option_is_refused(repo: Path) -> None:
    with pytest.raises(FreezeCheckError, match="not a git ref"):
        check_label_freeze("--all", repo)


def test_a_case_file_without_ids_is_an_error(repo: Path) -> None:
    write(repo, "eval/cases/own/b/03-bad.yaml", "label: {risk_class: high_risk}\n")
    with pytest.raises(FreezeCheckError, match=r"03-bad\.yaml"):
        check_label_freeze("main", repo)


def test_the_cli_exits_1_on_an_unlogged_change_and_0_once_logged(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(label_freeze, "REPO_DIR", repo)
    write(repo, "eval/cases/own/b/01-old.yaml", CASE_B01.replace("minimal_risk", "high_risk"))
    failed = CliRunner().invoke(app, ["evaluate", "label-freeze", "--base", "main"])
    assert failed.exit_code == 1
    assert "UNLOGGED: case own-b-01-old" in failed.output
    append_log(repo, log_row("own-b-01-old"))
    passed = CliRunner().invoke(app, ["evaluate", "label-freeze", "--base", "main"])
    assert passed.exit_code == 0, passed.output
    assert "1 approved cases changed" in passed.output


def test_the_cli_exits_2_on_a_bad_ref(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(label_freeze, "REPO_DIR", repo)
    result = CliRunner().invoke(app, ["evaluate", "label-freeze", "--base", "nope"])
    assert result.exit_code == 2


def _has_local_main() -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "main"],
        cwd=label_freeze.REPO_DIR,
        capture_output=True,
    )
    return completed.returncode == 0


@pytest.mark.skipif(not _has_local_main(), reason="no local main branch (CI's own job runs this)")
def test_this_repo_keeps_the_freeze_against_main() -> None:
    """A story branch runs the real check in its checks; CI runs it in the label-freeze job."""
    report = check_label_freeze("main")
    assert report.is_ok, [case.describe() for case in report.unlogged] + list(
        report.edited_log_rows
    )
