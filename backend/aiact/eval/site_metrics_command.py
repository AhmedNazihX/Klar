"""The `aiact evaluate site-metrics` command (P27), kept out of `aiact/cli.py`, which registers
it."""

import re
from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg
import typer

from aiact.eval import (
    head_to_head,
    head_to_head_command,
    head_to_head_report,
    head_to_head_sheet,
    records,
    report,
)
from aiact.eval.cases import CaseFileError
from aiact.eval.site_metrics import (
    REPORT_PATH,
    SITE_FILE,
    SiteMetricsError,
    head_to_head_figures,
    site_metrics,
    write_site_file,
)

EXPECTED_ERRORS = (
    SiteMetricsError,
    head_to_head_report.EngineRunError,
    report.RunNotFoundError,
    report.RunRecordError,
    records.DatabaseNotConfiguredError,
    FileNotFoundError,
)
"""Errors whose text names runs, counts and paths only: printed as they are."""
CASE_NAMING_ERRORS = (head_to_head.DrawError, head_to_head_sheet.SheetError, CaseFileError)
"""Errors whose text can name drawn case ids, Pile B's included: never printed (V11)."""
CASE_ID = re.compile(r"\b(cb|own|aai|acad)-")
"""A case id's start; the note goes into the public site file, so it may hold none."""
CASE_FILES_ERROR = (
    "Error: the draw, the answer sheet ({sheet}) or a case file doesn't fit ({kind}); run "
    "`aiact evaluate head-to-head check` for details"
)


def site_metrics_command(
    commission_run: Annotated[
        UUID,
        typer.Option(help="The stored held-out commission_b run whose figures are published."),
    ],
    head_to_head_run: Annotated[
        UUID,
        typer.Option(help="The stored engine run of the head-to-head draw (V10b)."),
    ],
    note: Annotated[
        str, typer.Option(help="Which runs are published and why, kept in the file as is.")
    ],
    report_url: Annotated[
        str,
        typer.Option(help="The final report's public URL, for the Method page's link."),
    ] = REPORT_PATH,
    output: Annotated[Path, typer.Option(help="Where the figures go.")] = SITE_FILE,
    draw_file: Annotated[
        Path, typer.Option(help="The committed case draw.")
    ] = head_to_head.DRAW_FILE,
    sheet: Annotated[
        Path, typer.Option(help="The checker's answer sheet.")
    ] = head_to_head_sheet.SHEET_FILE,
) -> None:
    """Write the site's accuracy figures (the landing and Method pages) from stored runs only:
    the Commission figures of --commission-run and the head-to-head of --head-to-head-run, each
    figure naming its run (read-only on the database, no model call; decision 024 addendum)."""
    if CASE_ID.search(note):
        typer.echo("Error: --note names a case id; the site file is public", err=True)
        raise typer.Exit(code=1)
    try:
        drawn, filled = head_to_head_command.checked_sheet(draw_file, sheet)
        cases = head_to_head_report.current_cases(drawn)
        with records.connect() as connection:
            engine = head_to_head_report.engine_column(connection, head_to_head_run, drawn)
            figures = head_to_head_figures(engine, filled, drawn, cases)
            metrics = site_metrics(connection, commission_run, figures, note, report_url)
    except CASE_NAMING_ERRORS as error:
        typer.echo(CASE_FILES_ERROR.format(sheet=sheet.name, kind=type(error).__name__), err=True)
        raise typer.Exit(code=1) from None
    except EXPECTED_ERRORS as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=1) from error
    write_site_file(metrics, output)
    typer.echo(f"Written: {output}")
