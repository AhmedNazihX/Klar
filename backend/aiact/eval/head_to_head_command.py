"""The `aiact evaluate head-to-head` commands (V10a, decision 036), kept out of `aiact/cli.py`,
which registers `app`: `draw` fixes the cases and writes the answer sheet, `check` validates the
sheet the user fills, `render` writes the report from it, with `--run-id` the engine column from a
stored run of the drawn cases (V10b; `aiact evaluate run --cases-from-draw` makes that run), saved
to the engine file that a later `render` without `--run-id` reads."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg
import typer

from aiact.eval import head_to_head, head_to_head_report, head_to_head_sheet, records, report
from aiact.eval.cases import CaseFileError

app = typer.Typer(no_args_is_help=True)

DrawOption = Annotated[Path, typer.Option(help="The committed case draw.")]
SheetOption = Annotated[Path, typer.Option(help="The answer sheet the user fills.")]


@app.callback()
def head_to_head_() -> None:
    """The head-to-head against the Commission's checker: draw, check the answers, render."""


@contextmanager
def _errors_exit() -> Iterator[None]:
    """Exit 1 with the message on the expected errors: a draw, a sheet or a case file that
    doesn't fit, or a missing file."""
    try:
        yield
    except (
        head_to_head.DrawError,
        head_to_head_sheet.SheetError,
        head_to_head_report.EngineRunError,
        report.RunNotFoundError,
        report.RunRecordError,
        records.DatabaseNotConfiguredError,
        CaseFileError,
        FileNotFoundError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error


@app.command("draw")
def draw(
    output: DrawOption = head_to_head.DRAW_FILE,
    sheet: SheetOption = head_to_head_sheet.SHEET_FILE,
) -> None:
    """Draw the cases from the labels-v1 tag by the committed seed and rule, and write the draw
    and an empty answer sheet.

    The draw is frozen: re-running changes nothing, and a different draw is refused. An existing
    sheet is never overwritten.
    """
    with _errors_exit():
        commit, cases = head_to_head.cases_at()
        drawn = head_to_head.make_draw(cases, commit)
        is_written = head_to_head.write_draw(drawn, output)
        is_sheet_written = head_to_head_sheet.write_template(drawn, sheet)
    steps = ", ".join(f"{step} {n}" for step, n in head_to_head.step_counts(drawn).items())
    typer.echo(
        f"Drawn: {len(drawn.cases)} cases from {drawn.labels_ref} ({commit[:12]}), "
        f"seed {drawn.seed}"
    )
    typer.echo(f"Cases per step: {steps}")
    typer.echo(f"{'Written' if is_written else 'Unchanged'}: {output}")
    typer.echo(f"{'Written' if is_sheet_written else 'Kept'}: {sheet}")


@app.command("check")
def check(
    draw_file: DrawOption = head_to_head.DRAW_FILE,
    sheet: SheetOption = head_to_head_sheet.SHEET_FILE,
    complete: Annotated[
        bool,
        typer.Option(
            "--complete", help="Also fail while a drawn case or a spot-check isn't run yet."
        ),
    ] = False,
) -> None:
    """Validate the answer sheet against the draw and say how many cases and spot-checks are
    run."""
    with _errors_exit():
        _, filled = checked_sheet(draw_file, sheet)
    run = sum(entry.is_run for entry in filled.cases)
    spot_checks = head_to_head_sheet.spot_checks_run(filled)
    wanted = head_to_head_sheet.SPOT_CHECK_COUNT
    typer.echo(
        f"Valid: {run} of {len(filled.cases)} cases run, {spot_checks} of {wanted} spot-checks run"
    )
    if not complete:
        return
    if run < len(filled.cases):
        typer.echo("Error: some drawn cases aren't run yet", err=True)
    if spot_checks < wanted:
        typer.echo("Error: some spot-checks aren't run yet", err=True)
    if run < len(filled.cases) or spot_checks < wanted:
        raise typer.Exit(code=1)


@app.command("render")
def render(
    draw_file: DrawOption = head_to_head.DRAW_FILE,
    sheet: SheetOption = head_to_head_sheet.SHEET_FILE,
    output: Annotated[
        Path, typer.Option(help="Where the report goes.")
    ] = head_to_head_report.REPORT_FILE,
    run_id: Annotated[
        UUID | None,
        typer.Option(
            help="A stored engine run of exactly the drawn cases (`aiact evaluate run "
            "--cases-from-draw`), completed, held-out: fills the engine column."
        ),
    ] = None,
    engine_file: Annotated[
        Path,
        typer.Option(
            help="The engine column's committed copy: written with --run-id, read without it."
        ),
    ] = head_to_head_report.ENGINE_FILE,
) -> None:
    """Validate the answer sheet and write the report from it; with --run-id the engine column
    comes from that stored run (read from DATABASE_URL) and is saved to --engine-file, else it
    comes from --engine-file when that exists, else it stays empty."""
    with _errors_exit():
        drawn, filled = checked_sheet(draw_file, sheet)
        cases = head_to_head_report.current_cases(drawn)
        if run_id is not None:
            engine = _engine_column(run_id, drawn)
        elif engine_file.is_file():
            engine = head_to_head_report.load_engine_file(engine_file, drawn)
        else:
            engine = None
        text = head_to_head_report.render_report(filled, drawn, cases, engine)
        if run_id is not None and engine is not None:
            head_to_head_report.write_engine_file(engine, drawn, engine_file)
            typer.echo(f"Written: {engine_file}")
    output.write_text(text, encoding="utf-8")
    typer.echo(f"Written: {output}")


def _engine_column(run_id: UUID, drawn: head_to_head.Draw) -> head_to_head_report.EngineColumn:
    """The engine column from the stored run; a database error names its type only (a
    connection error's text can name the server)."""
    try:
        with records.connect() as connection:
            return head_to_head_report.engine_column(connection, run_id, drawn)
    except psycopg.Error as error:
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=1) from error


def checked_sheet(
    draw_file: Path, sheet: Path
) -> tuple[head_to_head.Draw, head_to_head_sheet.HeadToHeadSheet]:
    """The draw and the sheet, checked against each other; screenshots sit next to the sheet."""
    drawn = head_to_head.load_draw(draw_file)
    filled = head_to_head_sheet.load_sheet(sheet)
    screenshots = sheet.parent / head_to_head_sheet.SCREENSHOT_DIR.name
    head_to_head_sheet.check_sheet(filled, drawn, date.today(), screenshots)
    return drawn, filled
