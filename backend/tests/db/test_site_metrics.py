"""`aiact evaluate site-metrics` (P27) on runs stored by the runner in the test database: the
Commission figures come from the stored run as its report computes them, the head-to-head from
the stored run of the draw, and a run that isn't a completed held-out `commission_b` run is
refused. The cases are made up, never benchmark cases; everything runs inside the test's
rolled-back transaction."""

from contextlib import nullcontext
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
import yaml
from psycopg.types.json import Jsonb
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import head_to_head, head_to_head_report, records
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.head_to_head import HEAD_TO_HEAD_BENCHMARK
from aiact.eval.metrics import CITATION_EXISTENCE_KEY
from aiact.eval.records import PostgresRunStore
from aiact.eval.report import RunNotFoundError
from aiact.eval.runner import DummyClassifier, ExcludeMode, RunOptions, run_benchmark
from aiact.eval.site_metrics import (
    HeadToHead,
    SiteCount,
    SiteFigure,
    SiteMetrics,
    SiteMetricsError,
    site_metrics,
)
from aiact.schemas import Language, RiskClass
from tests.db.test_head_to_head_engine import LOO
from tests.eval.test_head_to_head_report import (
    DRAW,
    DRAWN,
    HIGH,
    HIGH_HEADING,
    PROHIBITED,
    UNSURE_HEADING,
    run,
    sheet,
)

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
NOTE = "Run 1 of 2, the user's choice."
RUN_ON = "2026-10-01"
"""The checker runs' date: before today, as the sheet check requires."""
HEAD_TO_HEAD = HeadToHead(
    klar=SiteFigure(value=0.2, run_id=UUID("00000000-0000-4000-8000-0000000000aa")),
    checker=SiteFigure(value=0.3, run_id=UUID("00000000-0000-4000-8000-0000000000aa")),
    checker_name="A checker",
    cases=25,
)


def _case(
    case_id: str, risk_class: RiskClass, set_name: CaseSet = CaseSet.COMMISSION_B
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=set_name,
        language=Language.EN,
        description="Made-up description",
        label=CaseLabel(risk_class=risk_class),
        label_citation=("art:3:1",),
    )


# The dummy answers out of scope: 2 of 4 right, both high-risk cases too low.
CASES = (
    _case("cb-test-s1", RiskClass.HIGH_RISK),
    _case("cb-test-s2", RiskClass.HIGH_RISK),
    _case("cb-test-s3", RiskClass.OUT_OF_SCOPE),
    _case("cb-test-s4", RiskClass.OUT_OF_SCOPE),
)
# Three own cases, so their count differs from the Commission run's four.
OWN_CASES = tuple(_case(f"own-test-s{n}", RiskClass.OUT_OF_SCOPE, CaseSet.OWN) for n in range(1, 4))
# Citation existence as stored at run time: 3 of 4.
CITATIONS = {"cb-test-s1": True, "cb-test-s2": True, "cb-test-s3": True, "cb-test-s4": False}


def _stored(
    db: psycopg.Connection,
    cases: tuple[BenchmarkCase, ...],
    benchmark: CaseSet,
    exclude_mode: ExcludeMode,
) -> UUID:
    options = RunOptions(
        benchmark=benchmark,
        classifier_name="dummy",
        exclude_mode=exclude_mode,
        git_sha=GIT_SHA,
        concurrency=1,
    )
    return run_benchmark(cases, DummyClassifier(), PostgresRunStore(db), options, LOO).run_id


def _own_run(
    db: psycopg.Connection,
    benchmark: CaseSet = CaseSet.OWN,
    exclude_mode: ExcludeMode = ExcludeMode.HELDOUT,
) -> UUID:
    return _stored(db, OWN_CASES, benchmark, exclude_mode)


def _metrics(db: psycopg.Connection, commission: UUID, own: UUID | None = None) -> SiteMetrics:
    own_run = _own_run(db) if own is None else own
    return site_metrics(db, commission, HEAD_TO_HEAD, NOTE, own_run=own_run)


def _commission_run(
    db: psycopg.Connection,
    benchmark: CaseSet = CaseSet.COMMISSION_B,
    exclude_mode: ExcludeMode = ExcludeMode.HELDOUT,
) -> UUID:
    run_id = _stored(db, CASES, benchmark, exclude_mode)
    for case_id, exists in CITATIONS.items():
        db.execute(
            "update eval_case_results set scores = scores || %s where run_id = %s and case_id = %s",
            (Jsonb({CITATION_EXISTENCE_KEY: exists}), run_id, case_id),
        )
    return run_id


def _started(db: psycopg.Connection, run_id: UUID) -> str:
    row = db.execute("select started_at::date from eval_runs where id = %s", (run_id,)).fetchone()
    assert row is not None
    return row[0].isoformat()


def test_the_commission_figures_come_from_the_stored_run(db: psycopg.Connection) -> None:
    run_id, own = _commission_run(db), _own_run(db)
    metrics = _metrics(db, run_id, own)
    assert metrics.risk_class_accuracy == SiteFigure(value=0.5, run_id=run_id)
    assert metrics.false_low_risk_rate == SiteFigure(value=1.0, run_id=run_id)
    assert metrics.citations_exist == SiteFigure(value=0.75, run_id=run_id)
    assert metrics.head_to_head == HEAD_TO_HEAD
    assert metrics.scored_cases == SiteCount(count=4, run_id=run_id)
    assert metrics.own_cases == SiteCount(count=3, run_id=own)
    assert metrics.run_date.isoformat() == _started(db, run_id)
    assert metrics.run_ids == (run_id, own, HEAD_TO_HEAD.klar.run_id)
    assert (metrics.report, metrics.note) == ("eval/reports/final.md", NOTE)


def test_a_case_whose_scoring_failed_is_left_out_as_in_the_report(db: psycopg.Connection) -> None:
    run_id = _commission_run(db)
    db.execute(
        "update eval_case_results set scores = scores || %s where run_id = %s and case_id = %s",
        (Jsonb({"scoring_error": True}), run_id, "cb-test-s4"),
    )
    metrics = _metrics(db, run_id)
    assert metrics.risk_class_accuracy.value == pytest.approx(1 / 3)
    assert metrics.citations_exist.value == 1.0
    assert metrics.scored_cases.count == 3


def test_a_run_of_another_set_is_refused(db: psycopg.Connection) -> None:
    run_id = _commission_run(db, benchmark=CaseSet.OWN)
    with pytest.raises(SiteMetricsError, match="is a run of own, not of commission_b"):
        _metrics(db, run_id)


def test_a_gap_run_is_refused(db: psycopg.Connection) -> None:
    run_id = _commission_run(db, exclude_mode=ExcludeMode.ALL)
    with pytest.raises(SiteMetricsError, match="has exclude mode all, not heldout"):
        _metrics(db, run_id)


def test_a_run_that_did_not_complete_is_refused(db: psycopg.Connection) -> None:
    run_id = _commission_run(db)
    db.execute(
        "update eval_runs set config = config || %s where id = %s",
        (Jsonb({"outcome": {"status": "cost_cap_reached"}}), run_id),
    )
    with pytest.raises(SiteMetricsError, match="is cost_cap_reached, not completed"):
        _metrics(db, run_id)


def test_a_run_without_stored_citation_scores_is_refused(db: psycopg.Connection) -> None:
    run_id = _commission_run(db)
    db.execute(
        "update eval_case_results set scores = scores - %s where run_id = %s",
        (CITATION_EXISTENCE_KEY, run_id),
    )
    with pytest.raises(SiteMetricsError, match="counted no case for its citation existence"):
        _metrics(db, run_id)


def test_an_unknown_run_is_refused(db: psycopg.Connection) -> None:
    with pytest.raises(RunNotFoundError):
        _metrics(db, UUID("00000000-0000-4000-8000-00000000dead"))


def _head_to_head_run(db: psycopg.Connection) -> UUID:
    options = RunOptions(
        benchmark=HEAD_TO_HEAD_BENCHMARK,
        classifier_name="dummy",
        exclude_mode=ExcludeMode.HELDOUT,
        git_sha=GIT_SHA,
    )
    cases = list(DRAWN.values())
    return run_benchmark(cases, DummyClassifier(), PostgresRunStore(db), options, LOO).run_id


def _sheet_files(tmp_path: Path, *, is_complete: bool = True) -> list[str]:
    """The draw and a sheet the checker answered every drawn case of: the high-risk one `HIGH`
    right, every other "can't determine" (a miss); or, not complete, only two cases."""
    draw_path, sheet_path = tmp_path / "d.json", tmp_path / "s.yaml"
    head_to_head.write_draw(DRAW, draw_path)
    others = [c.case_id for c in DRAW.cases if c.case_id != HIGH]
    if not is_complete:
        others = [PROHIBITED]
    filled = sheet(
        run(HIGH, HIGH_HEADING, date=RUN_ON),
        *(run(case_id, UNSURE_HEADING, date=RUN_ON) for case_id in others),
    )
    sheet_path.write_text(yaml.safe_dump(filled.model_dump(mode="json")), encoding="utf-8")
    return ["--draw-file", str(draw_path), "--sheet", str(sheet_path)]


def _invoke(
    db: psycopg.Connection,
    tmp_path: Path,
    commission: UUID,
    engine: UUID,
    *extra: str,
    is_complete: bool = True,
) -> tuple[int, str, Path]:
    output = tmp_path / "accuracy.json"
    result = CliRunner().invoke(
        app,
        [
            *("evaluate", "site-metrics", *_sheet_files(tmp_path, is_complete=is_complete)),
            *("--commission-run", str(commission), "--head-to-head-run", str(engine)),
            *("--own-run", str(_own_run(db))),
            *("--note", NOTE, "--output", str(output), *extra),
        ],
    )
    return result.exit_code, result.output, output


def _patch_sources(db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(head_to_head_report, "current_cases", lambda draw: DRAWN)
    monkeypatch.setattr(records, "connect", lambda: nullcontext(db))


def test_the_command_writes_the_site_file_from_both_stored_runs(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_sources(db, monkeypatch)
    commission, engine = _commission_run(db), _head_to_head_run(db)
    url = "https://example.org/final.md"
    code, output, path = _invoke(db, tmp_path, commission, engine, "--report-url", url)
    assert code == 0, output
    text = path.read_text(encoding="utf-8")
    written = SiteMetrics.model_validate_json(text)
    assert written.risk_class_accuracy == SiteFigure(value=0.5, run_id=commission)
    assert written.false_low_risk_rate == SiteFigure(value=1.0, run_id=commission)
    assert written.citations_exist == SiteFigure(value=0.75, run_id=commission)
    # The dummy (out of scope) is right on 5 of the 25 drawn cases; the checker on 1.
    assert written.head_to_head == HeadToHead(
        klar=SiteFigure(value=0.2, run_id=engine),
        checker=SiteFigure(value=0.04, run_id=engine),
        checker_name="EU AI Act Compliance Checker",
        cases=25,
    )
    assert written.scored_cases == SiteCount(count=4, run_id=commission)
    assert written.own_cases.count == 3
    assert written.run_ids == (commission, written.own_cases.run_id, engine)
    assert written.note == NOTE
    assert written.report == url
    assert "cb-test" not in text and "Made-up description" not in text
    assert not any(case.case_id in text for case in DRAW.cases)


def test_the_command_refuses_a_head_to_head_run_that_is_not_the_draw(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_sources(db, monkeypatch)
    commission = _commission_run(db)
    code, output, path = _invoke(db, tmp_path, commission, commission)
    assert code == 1
    assert "is a run of commission_b, not of the head-to-head draw" in output
    assert not path.exists()


def test_the_command_refuses_a_commission_run_that_is_not_held_out(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_sources(db, monkeypatch)
    commission = _commission_run(db, exclude_mode=ExcludeMode.ALL)
    code, output, path = _invoke(db, tmp_path, commission, _head_to_head_run(db))
    assert code == 1
    assert "has exclude mode all, not heldout" in output
    assert not path.exists()


def test_the_command_refuses_a_checker_column_that_left_drawn_cases_unanswered(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_sources(db, monkeypatch)
    commission, engine = _commission_run(db), _head_to_head_run(db)
    code, output, path = _invoke(db, tmp_path, commission, engine, is_complete=False)
    assert code == 1
    assert "the checker column answered 2 of the 25 drawn cases" in output
    assert not path.exists()


def test_the_report_link_defaults_to_the_reports_path_in_the_repository(
    db: psycopg.Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_sources(db, monkeypatch)
    code, output, path = _invoke(db, tmp_path, _commission_run(db), _head_to_head_run(db))
    assert code == 0, output
    written = SiteMetrics.model_validate_json(path.read_text(encoding="utf-8"))
    assert written.report == "eval/reports/final.md"


@pytest.mark.parametrize(
    ("run", "message"),
    [
        ({"benchmark": CaseSet.COMMISSION_B}, "is a run of commission_b, not of own"),
        ({"exclude_mode": ExcludeMode.ALL}, "has exclude mode all, not heldout"),
    ],
)
def test_an_own_run_that_is_not_a_held_out_own_run_is_refused(
    db: psycopg.Connection, run: dict[str, object], message: str
) -> None:
    own = _own_run(db, **run)  # pyright: ignore[reportArgumentType]
    with pytest.raises(SiteMetricsError, match=message):
        _metrics(db, _commission_run(db), own)
