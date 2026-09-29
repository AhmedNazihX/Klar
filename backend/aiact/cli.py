"""The `aiact` command root. Scripts are subcommands per area: `aiact corpus …`, `aiact evaluate …`.

Each area adds its commands to its group here (for example `@corpus_app.command()`).
Help texts come from the callback docstrings.
"""

from collections.abc import Callable
from pathlib import Path
from subprocess import CalledProcessError
from typing import Annotated
from uuid import UUID

import psycopg
import typer

from aiact import db, deps
from aiact.corpus import embed as corpus_embed_module
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParseError, RawFileError, parse_all
from aiact.corpus.fetch import DEFAULT_MANIFEST, Fetcher, fetch_all, make_client
from aiact.eval import academic, citation_index, metrics, records, report, runner
from aiact.eval import split as eval_split
from aiact.eval.cases import CaseFileError, CaseSet, load_cases
from aiact.llm import EmbeddingError, LLMConfigError, OpenRouterEmbeddings
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


@corpus_app.command("guidelines")
def corpus_guidelines(
    manifest: Annotated[
        Path | None, typer.Option(help="Manifest to read [default: repo data/manifest.yaml]")
    ] = None,
    raw_dir: Annotated[
        Path | None, typer.Option(help="Where raw files are [default: $AIACT_DATA_DIR/raw]")
    ] = None,
    out_dir: Annotated[
        Path | None, typer.Option(help="Where JSONL goes [default: repo data/parsed]")
    ] = None,
    split: Annotated[
        Path | None,
        typer.Option(help="The committed split; only its pile_b list is read [default: repo]"),
    ] = None,
) -> None:
    """Parse the guideline PDFs (Docling) into section and worked-example chunks, one JSONL
    file per document and language; Pile B examples are kept and tagged as held out.

    Needs the optional `ingest` group: `uv sync --group ingest`."""
    # Imported here: docling-core and pandas load slowly, and no other command needs them.
    from aiact.corpus import guidelines
    from aiact.corpus.guideline_examples import ExampleCountError
    from aiact.corpus.guidelines_pdf import IngestNotInstalledError

    try:
        report = guidelines.parse_guidelines(
            manifest or DEFAULT_MANIFEST,
            raw_dir or get_settings().aiact_data_dir / "raw",
            out_dir or DEFAULT_PARSED_DIR,
            split or guidelines.DEFAULT_SPLIT_FILE,
        )
    except (
        RawFileError,
        guidelines.GuidelineError,
        ExampleCountError,
        IngestNotInstalledError,
        FileNotFoundError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    for label, chunks, examples in report.counts:
        typer.echo(f"{label}: {chunks} chunks ({examples} examples)")
    typer.echo(f"tagged held out (Pile B): {len(report.held_out_ids)}")
    typer.echo(" ".join(report.held_out_ids))
    typer.echo(
        f"written: {len(report.written)}, unchanged: {len(report.counts) - len(report.written)}"
    )


@corpus_app.command("load")
def corpus_load(
    manifest: Annotated[
        Path | None, typer.Option(help="Manifest to read [default: repo data/manifest.yaml]")
    ] = None,
    parsed_dir: Annotated[
        Path | None, typer.Option(help="Where the parsed JSONL is [default: repo data/parsed]")
    ] = None,
    stats: Annotated[
        Path | None,
        typer.Option(help="Where the row counts go [default: repo docs/corpus_stats.md]"),
    ] = None,
) -> None:
    """Load the parsed laws and guidelines into Postgres (documents, provisions) and write the
    row counts per document to docs/corpus_stats.md. Re-running changes nothing."""
    # Imported here: the guideline rows pull in docling-core, which loads slowly.
    from aiact.corpus import build as corpus_build
    from aiact.corpus import load as corpus_load_module

    stats_path = stats or corpus_load_module.STATS_FILE
    try:
        loads = corpus_build.build_all(
            manifest or DEFAULT_MANIFEST, parsed_dir or DEFAULT_PARSED_DIR
        )
        with db.connect() as connection:
            outcomes = corpus_load_module.load_all(connection, loads)
            unlisted = corpus_load_module.unlisted_documents(connection, loads)
            counts = corpus_load_module.corpus_stats(connection)
    except (corpus_build.LoadError, db.DatabaseNotConfiguredError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=1) from error
    for label, outcome in outcomes:
        typer.echo(f"{outcome:<9} {label}")
    for label in unlisted:
        typer.echo(f"Warning: {label} is in the database but not in the manifest; kept", err=True)
    typer.echo(corpus_load_module.render_stats(counts), nl=False)
    is_written = corpus_load_module.write_stats(counts, stats_path)
    typer.echo(f"{'Written' if is_written else 'Unchanged'}: {stats_path}")


@corpus_app.command("embed")
def corpus_embed(
    model: Annotated[
        str, typer.Option(help=f"The embedding arm: {' | '.join(corpus_embed_module.ARMS)}")
    ] = "qwen3",
    dims: Annotated[
        int | None,
        typer.Option(
            help=f"Vector size: {' | '.join(map(str, corpus_embed_module.DIMENSION_CHOICES))}"
            " [default: EMBEDDING_DIMENSIONS]"
        ),
    ] = None,
    doc_key: Annotated[
        list[str] | None, typer.Option(help="Embed only these documents (repeatable)")
    ] = None,
    batch_size: Annotated[
        int, typer.Option(min=1, max=256, help="Texts per request")
    ] = corpus_embed_module.DEFAULT_BATCH_SIZE,
) -> None:
    """Embed every provision row that has no current vector for the arm (skips rows already
    embedded with the same model, size and text), and log the tokens and cost."""
    size = dims or get_settings().embedding_dimensions
    arm = corpus_embed_module.ARMS.get(model)
    if arm is None or size not in corpus_embed_module.DIMENSION_CHOICES:
        typer.echo(f"Error: unknown --model {model!r} or --dims {size}", err=True)
        raise typer.Exit(code=2)
    try:
        embedder = OpenRouterEmbeddings(model=arm.model, provider=arm.provider, dimensions=size)
        with db.connect() as connection:
            if not corpus_embed_module.has_arm_index(connection, arm.model, size):
                typer.echo(
                    f"Warning: no HNSW index for {arm.model}/{size}; add one in a migration",
                    err=True,
                )
            result = corpus_embed_module.embed_corpus(
                connection, embedder, arm, size, doc_keys=doc_key, batch_size=batch_size
            )
    except (LLMConfigError, EmbeddingError, db.DatabaseNotConfiguredError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"{result.model}/{result.dims}: {result.texts_embedded} texts embedded for "
        f"{result.rows_embedded} rows in {result.batches} batches, {result.rows_reused} rows "
        f"reused; {result.tokens} tokens, ${result.cost_usd:.6f}"
    )
    for sha in result.too_long:
        typer.echo(f"Warning: text {sha} is too long for {result.model}; not embedded", err=True)


@eval_app.callback()
def eval_() -> None:
    """Benchmark split, runs and metrics."""


@eval_app.command("academic-import")
def eval_academic_import(
    source: Annotated[Path, typer.Argument(help="scenarios.json from the davidath repo")],
    out_dir: Annotated[
        Path | None, typer.Option(help="Where the YAML goes [default: repo eval/cases/academic]")
    ] = None,
    overrides: Annotated[
        Path, typer.Option(help="The spot-check label overrides to apply.")
    ] = academic.OVERRIDES_FILE,
) -> None:
    """Convert the academic benchmark's scenarios into cases, one YAML file per risk class,
    with the spot-check overrides applied."""
    out_path = out_dir or academic.ACADEMIC_DIR
    try:
        scenarios = academic.read_scenarios(source, academic.SOURCE_SHA256)
        cases = academic.build_cases(scenarios, academic.read_overrides(overrides))
    except CaseFileError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    for path in academic.write_cases(cases, out_path):
        typer.echo(f"written: {path}")
    tag = metrics.LOW_OR_OUT_OF_SCOPE_TAG
    typer.echo(f"{len(cases)} cases, {sum(tag in case.tags for case in cases)} tagged {tag}")


@eval_app.command("academic-sample")
def eval_academic_sample() -> None:
    """Print the seeded spot-check sample (5 cases per risk class) of the imported cases."""
    for case in academic.spotcheck_sample(load_cases(CaseSet.ACADEMIC)):
        typer.echo(case.id)


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
        with records.connect() as connection:
            index = citation_index.load_citation_index(connection)
            scorer = metrics.metric_scorer(citation_index.citation_checker(index))
            summary = runner.run_benchmark(
                cases, chosen, records.PostgresRunStore(connection), options, split, scorer
            )
    except (records.DatabaseNotConfiguredError, runner.SplitError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(
        f"run {summary.run_id}: {summary.status.value}, {summary.cases_scored}/"
        f"{summary.cases_planned} cases ({summary.cases_failed} failed), "
        f"${summary.cost_usd:.4f}, {summary.tokens} tokens"
    )
    if is_dirty:
        typer.echo("Warning: uncommitted changes; the recorded git_sha may not reproduce", err=True)


@eval_app.command("report")
def eval_report(
    run_id: Annotated[UUID, typer.Argument(help="The eval_runs id to report on")],
) -> None:
    """Print a stored run's deterministic metrics as a markdown table (read-only)."""
    try:
        with records.connect() as connection:
            text = report.run_report(connection, run_id)
    except (
        records.DatabaseNotConfiguredError,
        report.RunNotFoundError,
        report.RunRecordError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(text, nl=False)


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
