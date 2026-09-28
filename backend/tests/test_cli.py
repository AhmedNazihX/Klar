from typer.testing import CliRunner

from aiact.cli import app

runner = CliRunner()


def test_root_help_lists_command_groups() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "corpus" in result.stdout
    assert "evaluate" in result.stdout


def test_command_groups_are_invocable() -> None:
    for group in ("corpus", "evaluate"):
        result = runner.invoke(app, [group, "--help"])
        assert result.exit_code == 0, group
