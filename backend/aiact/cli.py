"""The `aiact` command root. Scripts are subcommands per area: `aiact corpus …`, `aiact eval …`.

Each area adds its commands to its group here (for example `@corpus_app.command()`).
Help texts come from the callback docstrings.
"""

from pathlib import Path
from typing import Annotated

import typer

from aiact.corpus.fetch import DEFAULT_MANIFEST, Fetcher, fetch_all, make_client
from aiact.settings import get_settings

app = typer.Typer(no_args_is_help=True)
corpus_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)

app.add_typer(corpus_app, name="corpus")
app.add_typer(eval_app, name="eval")


@app.callback()
def main() -> None:
    """AI Act Classification Assistant. Guidance, not legal advice."""


@corpus_app.callback()
def corpus() -> None:
    """Fetch, parse, load and embed the legal corpus."""


@corpus_app.command("fetch")
def corpus_fetch(
    manifest: Annotated[
        Path | None, typer.Option(help="Manifest to update [default: repo data/manifest.yaml]")
    ] = None,
    raw_dir: Annotated[
        Path | None, typer.Option(help="Where raw files go [default: $AIACT_DATA_DIR/raw]")
    ] = None,
) -> None:
    """Download the legal texts and guidelines, and update the manifest (idempotent)."""
    manifest_path = manifest or DEFAULT_MANIFEST
    raw_path = raw_dir or get_settings().aiact_data_dir / "raw"
    with make_client() as client:
        report = fetch_all(manifest_path, raw_path, Fetcher(client))
    for entry in report.manifest.documents:
        state = "present" if entry.available else "absent "
        typer.echo(f"{state} {entry.id}.{entry.language}  {entry.absent_reason or entry.sha256}")
    typer.echo(
        f"changed: {len(report.changed)}, failed: {len(report.failures)}, "
        f"manifest {'written' if report.manifest_written else 'unchanged'}: {manifest_path}"
    )
    for failure in report.failures:
        typer.echo(f"FAILED {failure}", err=True)
    if report.failures:
        raise typer.Exit(code=1)


@eval_app.callback()
def eval_() -> None:
    """Benchmark split, runs and metrics."""
