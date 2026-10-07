"""The generated SQL seed and `aiact obligations seed`."""

from pathlib import Path

from typer.testing import CliRunner

from aiact.cli import app
from aiact.obligations.list import OBLIGATIONS_FILE, ObligationTable, load_table
from aiact.obligations.seed import SEED_SQL_FILE, render_seed_sql, write_seed_sql

runner = CliRunner()

QUOTED = ObligationTable.model_validate(
    {
        "law_version": "amended",
        "checked_on": "2026-09-28",
        "dates_reviewed": False,
        "obligations": [
            {
                "key": "quoted",
                "roles": ["deployer"],
                "risk_classes": ["limited_risk"],
                "duty": "Tell people it's an AI system.",
                "duty_de": "Personen informieren.",
                "label_en": "Tell people it's AI",
                "label_de": "Personen informieren",
                "document": "art_50_3_disclosure",
                "article": "art:50:1",
                "applies_from": "2026-08-02",
            }
        ],
    }
)


def test_committed_seed_matches_the_yaml() -> None:
    """Fails when the YAML changed without `aiact obligations seed`."""
    assert SEED_SQL_FILE.read_text(encoding="utf-8") == render_seed_sql(load_table())


def test_seed_escapes_quotes_and_writes_nulls() -> None:
    sql = render_seed_sql(QUOTED)
    assert "'Tell people it''s an AI system.'" in sql
    assert (
        "('quoted', 0, 'deployer', 'limited_risk', null, 'Tell people it''s an AI system.', "
        "'art:50:1', '2026-08-02', null, false, null, null, 'amended', 'Tell people it''s AI', "
        "'Personen informieren', 'Personen informieren.', null, 'art_50_3_disclosure')"
    ) in sql
    assert "delete from public.obligations where law_version = 'amended';" in sql


def test_write_seed_sql_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "obligations.sql"
    assert write_seed_sql(QUOTED, target) is True
    assert write_seed_sql(QUOTED, target) is False


def test_cli_seed_writes_then_reports_unchanged(tmp_path: Path) -> None:
    output = tmp_path / "obligations.sql"
    args = ["obligations", "seed", "--source", str(OBLIGATIONS_FILE), "--output", str(output)]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "Written" in first.stdout
    second = runner.invoke(app, args)
    assert "Unchanged" in second.stdout
    assert output.read_text(encoding="utf-8") == SEED_SQL_FILE.read_text(encoding="utf-8")


def test_cli_seed_fails_on_an_invalid_file(tmp_path: Path) -> None:
    source = tmp_path / "bad.yaml"
    source.write_text("obligations: []\n", encoding="utf-8")
    args = ["obligations", "seed", "--source", str(source), "--output", str(tmp_path / "x.sql")]
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert not (tmp_path / "x.sql").exists()
