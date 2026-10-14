"""The `aiact evaluate head-to-head` commands (V10a, decision 036), kept out of `aiact/cli.py`,
which registers `app`: `draw` fixes the cases and writes the answer sheet, `check` validates the
sheet the user fills, `render` writes the report from it."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from aiact.eval import head_to_head, head_to_head_report, head_to_head_sheet
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
        bool, typer.Option("--complete", help="Also fail while a drawn case isn't run yet.")
    ] = False,
) -> None:
    """Validate the answer sheet against the draw and say how many cases are run."""
    with _errors_exit():
        _, filled = _checked(draw_file, sheet)
    run = sum(entry.is_run for entry in filled.cases)
    typer.echo(f"Valid: {run} of {len(filled.cases)} cases run")
    if complete and run < len(filled.cases):
        typer.echo("Error: some drawn cases aren't run yet", err=True)
        raise typer.Exit(code=1)


@app.command("render")
def render(
    draw_file: DrawOption = head_to_head.DRAW_FILE,
    sheet: SheetOption = head_to_head_sheet.SHEET_FILE,
    output: Annotated[
        Path, typer.Option(help="Where the report goes.")
    ] = head_to_head_report.REPORT_FILE,
) -> None:
    """Validate the answer sheet and write the report from it (the engine column stays empty
    until V10b)."""
    with _errors_exit():
        drawn, filled = _checked(draw_file, sheet)
        cases = head_to_head_report.current_cases(drawn)
        text = head_to_head_report.render_report(filled, drawn, cases)
    output.write_text(text, encoding="utf-8")
    typer.echo(f"Written: {output}")


def _checked(
    draw_file: Path, sheet: Path
) -> tuple[head_to_head.Draw, head_to_head_sheet.HeadToHeadSheet]:
    """The draw and the sheet, checked against each other; screenshots sit next to the sheet."""
    drawn = head_to_head.load_draw(draw_file)
    filled = head_to_head_sheet.load_sheet(sheet)
    screenshots = sheet.parent / head_to_head_sheet.SCREENSHOT_DIR.name
    head_to_head_sheet.check_sheet(filled, drawn, date.today(), screenshots)
    return drawn, filled
