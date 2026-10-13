"""The `aiact evaluate judged` command (V5), kept out of `aiact/cli.py`, which registers it."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

import psycopg
import typer

from aiact.eval import judged_run, records
from aiact.eval.answers import AnswerSourceError
from aiact.eval.judge import UNSURE_MARGIN, Judge, JudgeCheck
from aiact.eval.judged import CHECK_NAMES, JudgedRecordError, JudgedSettings
from aiact.llm import LLMConfigError
from aiact.settings import Settings, get_settings


def judged_settings(settings: Settings) -> JudgedSettings:
    """The judge this command runs: the configured models at the judge's own margin."""
    return JudgedSettings(
        jev_model=settings.judge_model,
        backup_model=settings.judge_backup_model,
        backup_provider=settings.judge_backup_provider,
        margin=UNSURE_MARGIN,
    )


@contextmanager
def _errors_exit() -> Iterator[None]:
    """Exit 2 on the expected errors, a database error by its type only (its text can name the
    server)."""
    try:
        yield
    except (
        records.DatabaseNotConfiguredError,
        AnswerSourceError,
        judged_run.JudgedRunNotFoundError,
        judged_run.JudgedRowError,
        judged_run.JudgedSettingsError,
        JudgedRecordError,
        LLMConfigError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error


def judged(
    run_id: Annotated[UUID, typer.Argument(help="The eval_runs id whose results to judge")],
    dry_run: Annotated[
        bool, typer.Option(help="Print the items and the cost estimate; make no call")
    ] = False,
    max_cost_usd: Annotated[
        float, typer.Option(min=0.000001, help="Start no new case once this much is spent")
    ] = judged_run.DEFAULT_MAX_COST_USD,
    concurrency: Annotated[
        int, typer.Option(min=1, max=judged_run.MAX_CONCURRENCY, help="Items judged at once")
    ] = judged_run.DEFAULT_CONCURRENCY,
) -> None:
    """Judge a stored run (V5): citation support and evidence tags on a classification run, Q&A
    support on a Q&A run. Cases already judged are skipped; `aiact evaluate report` shows the
    scores."""
    settings = get_settings()
    chosen = judged_settings(settings)
    options = judged_run.JudgedOptions(max_cost_usd=max_cost_usd, concurrency=concurrency)
    with _errors_exit(), records.connect() as connection:
        run = judged_run.load_run(connection, run_id)
        judged_run.check_settings(run, chosen)
        source = judged_run.corpus_source(connection, run.started_at.date())
        planned = judged_run.plan_run(run, source)
        _echo_plan(planned, chosen, max_cost_usd)
        if dry_run or not planned:
            return
        judge = Judge.from_settings(settings)
        store = judged_run.PostgresJudgedStore(connection)
        summary = judged_run.judge_run(run, planned, judge, chosen, store, options)
    _echo_summary(summary)


def _echo_plan(
    planned: tuple[judged_run.PlannedCase, ...], chosen: JudgedSettings, max_cost_usd: float
) -> None:
    counts = judged_run.item_counts(planned)
    items = sum(counts.values())
    estimate = judged_run.estimate_usd(planned, chosen.backup_model)
    cost = (
        "COST UNKNOWN"
        if estimate is None
        else f"estimated at most ${estimate:.4f} (3 characters a token, the backup on every item)"
    )
    typer.echo(
        f"{len(planned)} cases to judge, {items} items ({_per_check(counts)}) with "
        f"{chosen.jev_model} and {chosen.backup_model} on {chosen.backup_provider}, margin "
        f"{chosen.margin}; {cost} (cap ${max_cost_usd:.2f})"
    )
    if estimate is None:
        typer.echo("WARNING: no prices known for this backup model; check the cap", err=True)


def _per_check(counts: Mapping[JudgeCheck, int]) -> str:
    return ", ".join(f"{CHECK_NAMES[check]}: {count}" for check, count in counts.items()) or "none"


def _echo_summary(summary: judged_run.JudgedSummary) -> None:
    not_measured = sum(score.not_measured for score in summary.totals.values())
    typer.echo(
        f"{summary.cases_judged} of {summary.cases_planned} cases judged, {not_measured} items "
        f"not measured; ${summary.cost_usd:.4f}, {summary.tokens} tokens"
    )
    if summary.status is judged_run.JudgedStatus.COST_CAP_REACHED:
        typer.echo("Stopped at the cost cap; run again to go on", err=True)
    if summary.status is judged_run.JudgedStatus.UNREACHED:
        typer.echo(
            "Stopped: a judge's call reached no model (key, endpoint, guardrail or network); the "
            "case it was on isn't stored. Fix the route and run again to go on",
            err=True,
        )
