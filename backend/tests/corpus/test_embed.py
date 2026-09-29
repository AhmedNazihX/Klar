"""Batching, grouping and the `aiact corpus embed` option checks (no database needed; the run
itself is tested in tests/db/test_corpus_embed.py)."""

import pytest
from typer.testing import CliRunner

from aiact import cli
from aiact.corpus.embed import PendingText, batches, group_by_text, input_text, vector_literal


def _text(sha: str, length: int) -> PendingText:
    return PendingText(sha, "x" * length, (1,))


def test_input_text_joins_heading_and_body_like_the_content_hash():
    assert input_text("Article 5", "1. text") == "Article 5\n1. text"
    assert input_text(None, "1. text") == "1. text"
    assert input_text("", "1. text") == "1. text"


def test_rows_with_the_same_hash_share_one_text():
    rows = [(1, "a", "H", "t"), (2, "b", None, "u"), (3, "a", "H", "t")]
    assert group_by_text(rows) == (
        PendingText("a", "H\nt", (1, 3)),
        PendingText("b", "u", (2,)),
    )


def test_batches_close_at_the_batch_size():
    texts = [_text(str(i), 1) for i in range(5)]
    assert [len(b) for b in batches(texts, batch_size=2)] == [2, 2, 1]


def test_batches_close_before_the_character_budget_and_a_long_text_goes_alone():
    texts = [_text("a", 40), _text("b", 50), _text("c", 150), _text("d", 10)]
    assert [[t.content_sha256 for t in b] for b in batches(texts, 10, max_chars=100)] == [
        ["a", "b"],
        ["c"],
        ["d"],
    ]


def test_vector_literal_is_pgvector_text():
    assert vector_literal([0.6, -0.8]) == "[0.6,-0.8]"


@pytest.mark.parametrize("args", [["--model", "bert"], ["--dims", "768"]])
def test_embed_rejects_an_unknown_arm_or_size(args: list[str]):
    result = CliRunner().invoke(cli.app, ["corpus", "embed", *args])
    assert result.exit_code == 2
    assert "unknown --model" in result.output
