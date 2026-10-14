"""The `aiact evaluate appliedai-review` command (V9), kept out of `aiact/cli.py`, which
registers it."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg
import typer

from aiact.eval import records
from aiact.eval.appliedai_review import (
    REVIEW_FILE,
    NotAppliedAIRunError,
    Review,
    ReviewFormatError,
    load_review,
)
from aiact.eval.appliedai_review_report import render_review
from aiact.eval.report import RunNotFoundError, RunRecordError


@contextmanager
def _errors_exit() -> Iterator[None]:
    """Exit 2 on the expected errors, a database error by its type only (its text can name the
    server). Nothing is written."""
    try:
        yield
    except (
        records.DatabaseNotConfiguredError,
        RunNotFoundError,
        RunRecordError,
        NotAppliedAIRunError,
        ReviewFormatError,
    ) as error:
        typer.echo(f"Error: {error}. Nothing was written.", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error


def appliedai_review(
    run_id: Annotated[UUID, typer.Argument(help="The stored appliedai run to review")],
    out: Annotated[Path, typer.Option(help="The review file to write and read back")] = REVIEW_FILE,
    check: Annotated[
        bool, typer.Option(help="Write nothing; fail while a disagreement has no verdict")
    ] = False,
) -> None:
    """Draft or update the appliedAI disagreement review of a stored run (V9): every case, the
    disagreements with a verdict for the user to write, Annex I apart, and risk-class accuracy
    before and after excluding the cases marked outdated label or label error. Verdicts already
    written are kept (read-only on the database)."""
    with _errors_exit(), records.connect() as connection:
        review = load_review(connection, run_id, out)
    if check:
        _check(review, out)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_review(review), encoding="utf-8")
    typer.echo(
        f"{len(review.cases)} cases, {len(review.disagreements)} disagreements "
        f"({sum(case.is_annex_i for case in review.disagreements)} Annex I), "
        f"{len(review.missing)} without a verdict. Written: {out}"
    )


def _check(review: Review, out: Path) -> None:
    for case_id in review.missing:
        typer.echo(f"NO VERDICT: {case_id}", err=True)
    typer.echo(
        f"{out}: {len(review.disagreements)} disagreements, {len(review.missing)} without a "
        "verdict",
        err=bool(review.missing),
    )
    if review.missing:
        raise typer.Exit(code=1)
