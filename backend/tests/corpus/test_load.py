"""The corpus stats file and the `aiact corpus load` command's error paths (no database needed;
the loading itself is tested in tests/db/test_corpus_load.py)."""

from pathlib import Path

from typer.testing import CliRunner

from aiact import cli
from aiact.corpus.load import DocumentStats, render_stats, write_stats

STATS = (
    DocumentStats("ai-act", "en", "original", "final", 10, 10, 0, 0, 0, 10),
    DocumentStats("guide-high-risk-annex-iii", "en", None, "draft", 5, 5, 0, 3, 1, 0),
)


def test_render_stats_has_a_row_per_document_and_a_total():
    lines = render_stats(STATS).splitlines()
    assert lines[2] == "| ai-act | en | original | final | 10 | 10 | 0 | 0 | 0 | 10 |"
    assert lines[3] == "| guide-high-risk-annex-iii | en | - | draft | 5 | 5 | 0 | 3 | 1 | 0 |"
    assert lines[4] == "| **Total** | | | | 15 | 15 | 0 | 3 | 1 | 10 |"


def test_write_stats_writes_once(tmp_path: Path):
    path = tmp_path / "corpus_stats.md"
    assert write_stats(STATS, path)
    assert not write_stats(STATS, path)
    assert path.read_text(encoding="utf-8").startswith("# Corpus statistics\n")


def test_load_fails_cleanly_without_parsed_files(tmp_path: Path):
    result = CliRunner().invoke(cli.app, ["corpus", "load", "--parsed-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "is missing" in result.output
