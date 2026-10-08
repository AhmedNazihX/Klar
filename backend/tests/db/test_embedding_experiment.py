"""X1a: an embedding-arm run stored in the local Supabase Postgres, and the check that an arm has
corpus vectors. Everything runs inside the test's rolled-back transaction."""

from decimal import Decimal

import psycopg
import pytest

from aiact.corpus.embed import EmbeddingArm
from aiact.eval.experiments import embeddings as experiment
from aiact.eval.experiments.embeddings import (
    CONTEXT_RECALL,
    Arm,
    ArmNotEmbeddedError,
    ExperimentOptions,
    ExperimentSet,
    require_embedded,
    run_arm,
)
from aiact.eval.records import PostgresRunStore
from tests.engine.test_usage import FakeEmbeddings
from tests.eval.experiments.test_embeddings import FakeSearch, annex_query, similar

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def test_an_arm_run_stores_its_config_scores_and_means(db: psycopg.Connection) -> None:
    summary = run_arm(
        "qwen3-1024",
        ExperimentSet.QA,
        (annex_query("annex:III:2"), annex_query("annex:III:3:a")),
        FakeEmbeddings(),
        PostgresRunStore(db),
        ExperimentOptions(GIT_SHA),
        search=FakeSearch([similar("annex:III:2", 0.66)]),
    )
    run = db.execute(
        "select benchmark, config, cost_usd, tokens from eval_runs where id = %s",
        (summary.run_id,),
    ).fetchone()
    assert run is not None
    benchmark, config, cost_usd, tokens = run
    assert (benchmark, cost_usd, tokens) == ("embedding_qa", Decimal("0.000200"), 14)
    assert config["arm"] == "qwen3-1024"
    assert config["outcome"]["means"][CONTEXT_RECALL] == 0.5
    rows = db.execute(
        "select scores from eval_case_results where run_id = %s order by case_id",
        (summary.run_id,),
    ).fetchall()
    assert [row[0][CONTEXT_RECALL] for row in rows] == [1.0, 0.0]


def test_an_arm_with_corpus_vectors_passes(db: psycopg.Connection) -> None:
    stored = {
        tuple(row) for row in db.execute("select distinct model, dims from provision_embeddings")
    }
    embedded = [n for n, a in experiment.ARMS.items() if (a.corpus.model, a.dims) in stored]
    if not embedded:
        pytest.skip("the local corpus has no vectors for any arm")
    for name in embedded:
        require_embedded(db, name)


def test_an_arm_without_corpus_vectors_says_how_to_embed_it(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    absent = EmbeddingArm("test/absent-model", "p", 1000)
    monkeypatch.setitem(experiment.CORPUS_ARMS, "absent", absent)
    monkeypatch.setitem(experiment.ARMS, "absent-1024", Arm(absent, 1024, True))  # pyright: ignore[reportArgumentType]
    with pytest.raises(ArmNotEmbeddedError, match="aiact corpus embed --model absent --dims 1024"):
        require_embedded(db, "absent-1024")
