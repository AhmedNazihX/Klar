import hashlib
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from aiact.cli import app
from aiact.eval import academic

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


def academic_import(source: Path, tmp_path: Path) -> Result:
    overrides = ACADEMIC_FIXTURE.with_name("overrides.yaml")
    arguments = ["--out-dir", str(tmp_path / "academic"), "--overrides", str(overrides)]
    return runner.invoke(app, ["evaluate", "academic-import", str(source), *arguments])


def test_academic_import_writes_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_sha256 = hashlib.sha256(ACADEMIC_FIXTURE.read_bytes()).hexdigest()
    monkeypatch.setattr(academic, "SOURCE_SHA256", fixture_sha256)
    result = academic_import(ACADEMIC_FIXTURE, tmp_path)
    assert result.exit_code == 0, result.output
    assert "4 cases, 0 tagged scoring:low-or-out-of-scope" in result.stdout
    assert len(list((tmp_path / "academic").glob("*.yaml"))) == 4


@pytest.mark.parametrize("source", ["fixture", "missing", "directory"])
def test_academic_import_reports_bad_input(tmp_path: Path, source: str) -> None:
    paths = {"fixture": ACADEMIC_FIXTURE, "missing": tmp_path / "x.json", "directory": tmp_path}
    result = academic_import(paths[source], tmp_path)
    assert result.exit_code == 1
    assert "Error: " in result.stderr
