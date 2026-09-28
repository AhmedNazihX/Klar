"""The `aiact` command root. Scripts are subcommands per area: `aiact corpus …`, `aiact evaluate …`.

Each area adds its commands to its group here (for example `@corpus_app.command()`).
Help texts come from the callback docstrings.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from aiact import deps
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParseError, RawFileError, parse_all
from aiact.corpus.fetch import DEFAULT_MANIFEST, Fetcher, fetch_all, make_client
from aiact.eval import split as eval_split
from aiact.obligations import list as obligations_list
from aiact.obligations import seed as obligations_seed
from aiact.settings import get_settings

app = typer.Typer(no_args_is_help=True)
corpus_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)
deps_app = typer.Typer(no_args_is_help=True)
obligations_app = typer.Typer(no_args_is_help=True)

app.add_typer(corpus_app, name="corpus")
app.add_typer(eval_app, name="evaluate")
app.add_typer(deps_app, name="deps")
app.add_typer(obligations_app, name="obligations")


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
        state = {True: "present", False: "absent ", None: "FAILED "}[entry.available]
        detail = entry.sha256 or entry.absent_reason or entry.fetch_error
        typer.echo(f"{state} {entry.id}.{entry.language}  {detail}")
    typer.echo(
        f"changed: {len(report.changed)}, failed: {len(report.failures)}, "
        f"manifest {'written' if report.manifest_written else 'unchanged'}: {manifest_path}"
    )
    for failure in report.failures:
        typer.echo(f"FAILED {failure}", err=True)
    if report.failures:
        raise typer.Exit(code=1)


@corpus_app.command("parse")
def corpus_parse(
    manifest: Annotated[
        Path | None, typer.Option(help="Manifest to read [default: repo data/manifest.yaml]")
    ] = None,
    raw_dir: Annotated[
        Path | None, typer.Option(help="Where raw files are [default: $AIACT_DATA_DIR/raw]")
    ] = None,
    out_dir: Annotated[
        Path | None, typer.Option(help="Where JSONL goes [default: repo data/parsed]")
    ] = None,
) -> None:
    """Parse the EUR-Lex laws into provisions, one JSONL file per document and language."""
    out_path = out_dir or DEFAULT_PARSED_DIR
    try:
        report = parse_all(
            manifest or DEFAULT_MANIFEST, raw_dir or get_settings().aiact_data_dir / "raw", out_path
        )
    except (RawFileError, ParseError, FileNotFoundError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    for label, count in report.counts:
        typer.echo(f"{label}: {count} provisions")
    typer.echo(
        f"written: {len(report.written)}, unchanged: {len(report.counts) - len(report.written)}"
    )


@eval_app.callback()
def eval_() -> None:
    """Benchmark split, runs and metrics."""


@eval_app.command("split")
def eval_split_command(
    examples: Annotated[
        Path, typer.Option(help="The Commission example rows to split.")
    ] = eval_split.EXAMPLES_FILE,
    output: Annotated[Path, typer.Option(help="Where the split goes.")] = eval_split.SPLIT_FILE,
    seed: Annotated[int, typer.Option(help="The shuffle seed.")] = eval_split.DEFAULT_SEED,
    pile_b_fraction: Annotated[
        float, typer.Option(help="The share of each stratum held out as Pile B.")
    ] = eval_split.DEFAULT_PILE_B_FRACTION,
) -> None:
    """Split the Commission examples into Pile A and Pile B, stratified by area x verdict.

    The written split is frozen: re-running with the same inputs changes nothing, and a
    different assignment is refused.
    """
    try:
        rows = eval_split.load_examples(examples)
        split = eval_split.make_split(rows, seed, pile_b_fraction)
        is_written = eval_split.write_split(split, output)
    except (eval_split.SplitError, FileNotFoundError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Pile A: {len(split.pile_a)}, Pile B: {len(split.pile_b)} (seed {split.seed})")
    typer.echo(f"{'Written' if is_written else 'Unchanged'}: {output}")


@obligations_app.callback()
def obligations() -> None:
    """The obligations table: duties per role and risk class."""


@obligations_app.command("seed")
def obligations_seed_command(
    source: Annotated[
        Path, typer.Option(help="The obligations YAML.")
    ] = obligations_list.OBLIGATIONS_FILE,
    output: Annotated[
        Path, typer.Option(help="Where the SQL seed goes.")
    ] = obligations_seed.SEED_SQL_FILE,
) -> None:
    """Validate the obligations YAML and regenerate the SQL seed `supabase db reset` loads."""
    try:
        table = obligations_list.load_table(source)
        is_written = obligations_seed.write_seed_sql(table, output)
    except obligations_list.ObligationsError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{len(table.rows())} rows from {len(table.obligations)} entries")
    typer.echo(f"{'Written' if is_written else 'Unchanged'}: {output}")


@deps_app.callback()
def deps_() -> None:
    """Generate and check docs/DEPENDENCIES.md from the lockfile."""


LockOption = typer.Option(deps.LOCK_PATH, "--lock", help="The uv.lock to read.")
OutputOption = typer.Option(deps.OUTPUT_PATH, "--output", help="The manifest to write or check.")
LicencesOption = typer.Option(
    deps.LICENCES_PATH, "--licences", help="The licence cache (name==version to licence, summary)."
)


def _or_exit[T](action: Callable[[], T]) -> T:
    """Run a deps action; a missing or unreadable input file exits 2 with the reason."""
    try:
        return action()
    except (FileNotFoundError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error


@deps_app.command("generate")
def deps_generate(
    lock: Path = LockOption, output: Path = OutputOption, licences: Path = LicencesOption
) -> None:
    """Update the licence cache (installed metadata, else PyPI) and write docs/DEPENDENCIES.md."""
    is_changed = _or_exit(lambda: deps.generate(lock, output, licences))
    typer.echo(f"{'Updated' if is_changed else 'Unchanged'}: {output}")


@deps_app.command("check")
def deps_check(
    lock: Path = LockOption, output: Path = OutputOption, licences: Path = LicencesOption
) -> None:
    """Exit non-zero when docs/DEPENDENCIES.md or the licence cache is stale. Works offline."""
    result = _or_exit(lambda: deps.check(lock, output, licences))
    typer.echo(result.message, err=not result.is_fresh)
    if not result.is_fresh:
        raise typer.Exit(code=1)
