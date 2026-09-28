"""The `aiact` command root. Scripts are subcommands per area: `aiact corpus …`, `aiact eval …`.

Each area adds its commands to its group here (for example `@corpus_app.command()`).
Help texts come from the callback docstrings.
"""

from collections.abc import Callable
from pathlib import Path
from subprocess import CalledProcessError
from typing import Annotated

import typer

from aiact import deps
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParseError, RawFileError, parse_all
from aiact.corpus.fetch import DEFAULT_MANIFEST, Fetcher, fetch_all, make_client
from aiact.eval import records, runner
from aiact.eval.cases import CaseFileError, CaseSet
from aiact.settings import get_settings

app = typer.Typer(no_args_is_help=True)
corpus_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)
deps_app = typer.Typer(no_args_is_help=True)

app.add_typer(corpus_app, name="corpus")
app.add_typer(eval_app, name="eval")
app.add_typer(deps_app, name="deps")


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


@eval_app.command("run")
def eval_run(
    set_name: Annotated[CaseSet, typer.Option("--set", help="The case set to run")],
    classifier: Annotated[
        str, typer.Option(help=f"One of: {', '.join(sorted(runner.CLASSIFIERS))}")
    ],
    subset: Annotated[
        int | None, typer.Option(min=1, help="Run a seeded random sample of N cases")
    ] = None,
    exclude_mode: Annotated[
        runner.ExcludeMode,
        typer.Option(help="heldout: keep held-out examples out of retrieval; all: exclude none"),
    ] = runner.ExcludeMode.HELDOUT,
    concurrency: Annotated[
        int, typer.Option(min=1, max=runner.MAX_CONCURRENCY, help="Cases in flight at once")
    ] = runner.DEFAULT_CONCURRENCY,
    max_cost_usd: Annotated[
        float, typer.Option(min=0.000001, help="Start no new case once this much is spent")
    ] = runner.DEFAULT_MAX_COST_USD,
    seed: Annotated[int, typer.Option(help="Seed for the --subset sample")] = 0,
) -> None:
    """Run a classifier over a benchmark set and record it in eval_runs / eval_case_results."""
    try:
        chosen = runner.build_classifier(classifier)
        split = runner.load_split() if exclude_mode is runner.ExcludeMode.HELDOUT else None
        cases = runner.load_benchmark(set_name)
        git_sha, is_dirty = runner.current_git_state()
    except (
        runner.ClassifierUnavailableError,
        runner.SplitError,
        CaseFileError,
        FileNotFoundError,
        CalledProcessError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    options = runner.RunOptions(
        benchmark=set_name,
        classifier_name=classifier,
        exclude_mode=exclude_mode,
        git_sha=git_sha,
        is_git_dirty=is_dirty,
        subset=subset,
        seed=seed,
        concurrency=concurrency,
        max_cost_usd=max_cost_usd,
    )
    try:
        connection = records.connect()
    except records.DatabaseNotConfiguredError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    with connection:
        try:
            summary = runner.run_benchmark(
                cases, chosen, records.PostgresRunStore(connection), options, split
            )
        except runner.SplitError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(code=2) from error
    typer.echo(
        f"run {summary.run_id}: {summary.status.value}, {summary.cases_scored}/"
        f"{summary.cases_planned} cases ({summary.cases_failed} failed), "
        f"${summary.cost_usd:.4f}, {summary.tokens} tokens"
    )
    if is_dirty:
        typer.echo("Warning: uncommitted changes; the recorded git_sha may not reproduce", err=True)


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
