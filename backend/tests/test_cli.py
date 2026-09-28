from pathlib import Path

from typer.testing import CliRunner

from aiact.cli import app

runner = CliRunner()
ACADEMIC_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "academic" / "scenarios.json"


def test_root_help_lists_command_groups() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "corpus" in result.stdout
    assert "evaluate" in result.stdout


def test_command_groups_are_invocable() -> None:
    for group in ("corpus", "evaluate"):
        result = runner.invoke(app, [group, "--help"])
        assert result.exit_code == 0, group


def test_academic_import_writes_cases_and_reports_bad_input(tmp_path: Path) -> None:
    out_dir = tmp_path / "academic"
    result = runner.invoke(
        app, ["evaluate", "academic-import", str(ACADEMIC_FIXTURE), "--out-dir", str(out_dir)]
    )
    assert result.exit_code == 0, result.output
    assert "4 cases" in result.stdout
    assert len(list(out_dir.glob("*.yaml"))) == 4
    missing = runner.invoke(app, ["evaluate", "academic-import", str(tmp_path / "missing.json")])
    assert missing.exit_code == 1
