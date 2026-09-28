from datetime import UTC, datetime
from uuid import UUID

from aiact.eval.metrics import summarize
from aiact.eval.report import RunInfo, render_markdown
from aiact.schemas import Citation, RiskClass, Role
from tests.eval.outcomes import HIGH_ANNEX_POINT, case, outcome, result

INFO = RunInfo(
    id=UUID("00000000-0000-4000-8000-000000000001"),
    benchmark="own",
    git_sha="0123456789abcdef0123456789abcdef01234567",
    started_at=datetime(2026, 9, 28, 12, 0, tzinfo=UTC),
    model="openai/gpt-6-luna",
)


def always(citation: Citation) -> bool:
    return True


def test_report_is_a_markdown_table_of_every_metric() -> None:
    outcomes = [
        outcome(case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)),
        outcome(case("b"), result(RiskClass.MINIMAL_RISK)),
        outcome(case("c"), failed=True),
    ]
    report = render_markdown(INFO, summarize(outcomes, always))
    lines = report.splitlines()
    assert lines[0] == f"## Run {INFO.id}"
    assert "- Cases: 3 (1 failed)" in lines
    assert "| Metric | Value | Count |" in lines
    assert "| Risk-class accuracy | 33.3% | 1/3 |" in lines
    assert "| False-low-risk rate | 50.0% | 1/2 |" in lines
    assert "| Annex point accuracy | 100.0% | 1/1 |" in lines
    assert "| Consistency | n/a | 0/0 |" in lines
    assert "| Citation existence | 100.0% | 12/12 |" in lines
    assert "| Ambiguous answered needs-more-information | 0 | |" in lines
    table = [line for line in lines if line.startswith("| ")]
    assert len(table) == 15  # header, separator and 13 metric rows


def test_report_names_no_description() -> None:
    report = render_markdown(INFO, summarize([outcome(case("a"))], always))
    assert "made-up system" not in report.lower()
