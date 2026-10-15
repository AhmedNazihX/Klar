"""The `aiact evaluate breakdown` command (W1), kept out of `aiact/cli.py`, which registers it."""

from typing import Annotated
from uuid import UUID

import psycopg
import typer

from aiact.eval import breakdown, records, report


def breakdown_command(
    run_id: Annotated[UUID, typer.Argument(help="The eval_runs id to break down")],
    by: Annotated[
        breakdown.GroupBy,
        typer.Option(help="Group the cases by language, business function or Commission area"),
    ],
) -> None:
    """Print a stored run's metrics per language, business function or Commission area, with
    each group's case count (read-only, W1)."""
    try:
        with records.connect() as connection:
            text = breakdown.breakdown_report(connection, run_id, by)
    except (
        records.DatabaseNotConfiguredError,
        report.RunNotFoundError,
        report.RunRecordError,
        breakdown.NotAClassificationRunError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(text, nl=False)
