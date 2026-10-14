"""The head-to-head engine column (V10b) from runs stored in local Postgres: `aiact evaluate run
--cases-from-draw` with the dummy classifier (free), then `engine_column` and `render --run-id`.
The cases are the made-up test pool's, never benchmark cases."""

import threading
from contextlib import nullcontext
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import citation_index, head_to_head, head_to_head_report, records, runner
from aiact.eval.head_to_head import HEAD_TO_HEAD_BENCHMARK
from aiact.eval.head_to_head_report import EngineRunError, engine_column, render_report
from aiact.eval.head_to_head_sheet import load_sheet
from aiact.eval.records import PostgresRunStore
from aiact.eval.report import RunNotFoundError
from aiact.eval.runner import (
    Classification,
    ClassifierInfo,
    ClassifierInput,
    DummyClassifier,
    ExcludeMode,
    RunOptions,
    run_benchmark,
)
from aiact.eval.split import Split, SplitMode
from aiact.schemas import RiskClass
from tests.eval.head_to_head_pool import make_case
from tests.eval.test_head_to_head_report import DRAW, DRAWN, write_sheet_files

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
LOO = Split(
    mode=SplitMode.LOO,
    seed=1,
    pile_b_fraction=0.5,
    stratify_by=("area",),
    pile_a=(),
    pile_b=(),
)


def _patch_sources(db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """The draw, its cases and the split are the test's; the database is the test's connection."""
    monkeypatch.setattr(head_to_head, "load_draw", lambda path=None: DRAW)
    monkeypatch.setattr(head_to_head_report, "current_cases", lambda draw: DRAWN)
    monkeypatch.setattr(runner, "load_split", lambda: LOO)
    monkeypatch.setattr(citation_index, "load_citation_index", lambda connection: frozenset())
    monkeypatch.setattr(records, "connect", lambda: nullcontext(db))


def _stored_run(
    db: psycopg.Connection,
    benchmark: str = HEAD_TO_HEAD_BENCHMARK,
    exclude_mode: ExcludeMode = ExcludeMode.HELDOUT,
    subset: int | None = None,
    extra: int = 0,
) -> UUID:
    cases = [
        *DRAWN.values(),
        *(make_case(f"own-extra-{n}", RiskClass.HIGH_RISK) for n in range(extra)),
    ]
    options = RunOptions(
        benchmark=benchmark,
        classifier_name="dummy",
        exclude_mode=exclude_mode,
        git_sha=GIT_SHA,
        subset=subset,
    )
    return run_benchmark(cases, DummyClassifier(), PostgresRunStore(db), options, LOO).run_id


def test_a_run_of_the_draw_records_exactly_the_drawn_cases_as_head_to_head(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_sources(db, monkeypatch)
    result = CliRunner().invoke(
        app, ["evaluate", "run", "--cases-from-draw", "--classifier", "dummy"]
    )
    assert result.exit_code == 0, result.output
    run_id = UUID(result.stdout.split()[1].rstrip(":"))
    row = db.execute(
        "select benchmark, config ->> 'exclude_mode', config -> 'outcome' ->> 'status'"
        " from eval_runs where id = %s",
        (run_id,),
    ).fetchone()
    assert row == ("head_to_head", "heldout", "completed")
    stored = db.execute(
        "select case_id from eval_case_results where run_id = %s order by case_id", (run_id,)
    ).fetchall()
    assert [case_id for (case_id,) in stored] == sorted(c.case_id for c in DRAW.cases)


def test_render_with_the_run_id_fills_the_engine_column_from_that_run(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_sources(db, monkeypatch)
    run_id = _stored_run(db)
    sheet_files, output = write_sheet_files(tmp_path), tmp_path / "r.md"
    result = CliRunner().invoke(
        app,
        [
            *("evaluate", "head-to-head", "render", *sheet_files),
            *("--output", str(output), "--run-id", str(run_id)),
        ],
    )
    assert result.exit_code == 0, result.output
    column = engine_column(db, run_id, DRAW)
    assert column.classes == {c.case_id: RiskClass.OUT_OF_SCOPE for c in DRAW.cases}
    assert (column.failed, column.run.id, column.run.classifier) == (0, run_id, "dummy")
    text = output.read_text(encoding="utf-8")
    assert text == render_report(load_sheet(tmp_path / "s.yaml"), DRAW, DRAWN, column)
    assert "| Engine | 25 of 25 | 20.0% (5/25) |" in text
    assert f"Engine: stored run `{run_id}` (classifier `dummy`, model `None`" in text
    saved = head_to_head_report.load_engine_file(tmp_path / "e.json", DRAW)
    assert (saved.classes, saved.failed, saved.run.id) == (column.classes, 0, run_id)
    assert render_report(load_sheet(tmp_path / "s.yaml"), DRAW, DRAWN, saved) == text


@pytest.mark.parametrize(
    ("run", "message"),
    [
        ({"benchmark": "own"}, "is a run of own, not of the head-to-head draw"),
        ({"exclude_mode": ExcludeMode.ALL}, "has exclude mode all, not heldout"),
        ({"subset": 24}, "holds 24 of the 25 drawn cases and 0 other cases"),
        ({"extra": 1}, "holds 25 of the 25 drawn cases and 1 other cases"),
    ],
)
def test_a_run_that_is_not_exactly_a_held_out_run_of_the_draw_is_refused(
    db: psycopg.Connection, run: dict[str, object], message: str
) -> None:
    run_id = _stored_run(db, **run)  # pyright: ignore[reportArgumentType]
    with pytest.raises(EngineRunError, match=message):
        engine_column(db, run_id, DRAW)


def test_a_run_that_did_not_complete_is_refused(db: psycopg.Connection) -> None:
    run_id = _stored_run(db)
    db.execute(
        "update eval_runs set config = config || %s where id = %s",
        (Jsonb({"outcome": {"status": "cost_cap_reached"}}), run_id),
    )
    with pytest.raises(EngineRunError, match="is cost_cap_reached, not completed"):
        engine_column(db, run_id, DRAW)


def test_an_unknown_run_is_refused(db: psycopg.Connection) -> None:
    with pytest.raises(RunNotFoundError):
        engine_column(db, UUID("00000000-0000-4000-8000-00000000dead"), DRAW)


class FailsFirstClassifier:
    """The dummy's answer, but the first call fails (as a timed-out model call would)."""

    info = ClassifierInfo(model=None)

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls = 0

    def classify(self, request: ClassifierInput) -> Classification:
        with self._lock:
            self._calls += 1
            is_first = self._calls == 1
        if is_first:
            raise RuntimeError("model timed out")
        return DummyClassifier().classify(request)


def test_a_case_that_failed_in_the_run_is_left_out_and_counted(db: psycopg.Connection) -> None:
    options = RunOptions(
        benchmark=HEAD_TO_HEAD_BENCHMARK,
        classifier_name="dummy",
        exclude_mode=ExcludeMode.HELDOUT,
        git_sha=GIT_SHA,
        concurrency=1,
    )
    store = PostgresRunStore(db)
    run_id = run_benchmark(list(DRAWN.values()), FailsFirstClassifier(), store, options, LOO).run_id
    column = engine_column(db, run_id, DRAW)
    first = min(c.case_id for c in DRAW.cases)
    assert column.failed == 1
    assert first not in column.classes and len(column.classes) == 24
