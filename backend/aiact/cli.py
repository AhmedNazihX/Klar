"""The `aiact` command root. Scripts are subcommands per area: `aiact corpus …`, `aiact evaluate …`.

Each area adds its commands to its group here (for example `@corpus_app.command()`).
Help texts come from the callback docstrings.
"""

from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from subprocess import CalledProcessError
from typing import Annotated
from uuid import UUID

import psycopg
import typer
from langsmith.utils import LangSmithError

from aiact import db, deps
from aiact.corpus import embed as corpus_embed_module
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, ParseError, RawFileError, parse_all
from aiact.corpus.fetch import DEFAULT_MANIFEST, Fetcher, fetch_all, make_client
from aiact.engine.usage import UsageMeter
from aiact.eval import (
    academic,
    citation_index,
    isolation,
    label_freeze,
    metrics,
    ragas_metrics,
    records,
    report,
    runner,
    similarity,
    tool_calls,
)
from aiact.eval import split as eval_split
from aiact.eval.cases import CASES_DIR, CaseFileError, CaseSet, load_cases, load_qa_items
from aiact.eval.experiments import embeddings as embedding_experiment
from aiact.eval.experiments import smoke, smoke_recheck, smoke_refusals, smoke_verdict
from aiact.eval.experiments.smoke_served import VerifyAll
from aiact.llm import EmbeddingError, LLMConfigError, OpenRouterEmbeddings
from aiact.llm.generations import GenerationLookup
from aiact.obligations import list as obligations_list
from aiact.obligations import seed as obligations_seed
from aiact.settings import get_settings

app = typer.Typer(no_args_is_help=True)
corpus_app = typer.Typer(no_args_is_help=True)
eval_app = typer.Typer(no_args_is_help=True)
deps_app = typer.Typer(no_args_is_help=True)
obligations_app = typer.Typer(no_args_is_help=True)
mcp_app = typer.Typer(no_args_is_help=True)
api_app = typer.Typer(no_args_is_help=True)

app.add_typer(corpus_app, name="corpus")
app.add_typer(eval_app, name="evaluate")
app.add_typer(deps_app, name="deps")
app.add_typer(obligations_app, name="obligations")
app.add_typer(mcp_app, name="mcp")
app.add_typer(api_app, name="api")


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


@eval_app.command("label-freeze")
def eval_label_freeze(
    base: Annotated[
        str,
        typer.Option(help="The ref to compare with; its merge base with HEAD is used (e.g. main)"),
    ],
) -> None:
    """Fail when an approved case (one under eval/cases/ at the base) changed without a new row in
    eval/LABEL_CHANGES.md (decision 017). New cases need no row."""
    try:
        result = label_freeze.check_label_freeze(base)
    except label_freeze.FreezeCheckError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    for row in result.edited_log_rows:
        typer.echo(f"LOG ROW REMOVED OR EDITED (the log is append-only): {row}", err=True)
    for mismatch in result.bulk_mismatches:
        typer.echo(f"BULK COUNT MISMATCH: {mismatch}", err=True)
    for case in result.unlogged:
        typer.echo(f"UNLOGGED: {case.describe()}", err=True)
    summary = (
        f"{len(result.changed)} approved cases changed since {result.base_sha[:12]}, "
        f"{len(result.unlogged)} without a new row in {label_freeze.LOG_PATH}"
    )
    typer.echo(summary, err=not result.is_ok)
    if not result.is_ok:
        raise typer.Exit(code=1)


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
        typer.Option(
            help="heldout: keep held-out examples out of retrieval; "
            "all: the gap run, retrieval sees every example, held-out ones included"
        ),
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


@eval_app.command("ragas")
def eval_ragas(
    subset: Annotated[int | None, typer.Option(min=1, help="A seeded sample of N items")] = None,
    top_k: Annotated[
        int, typer.Option(min=1, max=ragas_metrics.MAX_TOP_K, help="Search hits per question")
    ] = ragas_metrics.DEFAULT_TOP_K,
    max_cost_usd: Annotated[
        float, typer.Option(min=0.000001, help="Start no new item once this much is spent")
    ] = ragas_metrics.DEFAULT_MAX_COST_USD,
    seed: Annotated[int, typer.Option(help="Seed for the --subset sample")] = 0,
    arm: Annotated[
        str | None,
        typer.Option(
            help=f"Search with this embedding arm (X1a): {' | '.join(embedding_experiment.ARMS)}"
            " [default: the EMBEDDING_* settings]"
        ),
    ] = None,
) -> None:
    """Score retrieval and answers on the Q&A set with RAGAS and record the run (V6)."""
    if arm is not None and arm not in embedding_experiment.ARMS:
        typer.echo(f"Error: unknown --arm {arm!r}", err=True)
        raise typer.Exit(code=2)
    try:
        items = load_qa_items()
        git_sha, is_dirty = runner.current_git_state()
        options = ragas_metrics.RagasOptions(git_sha, is_dirty, subset, seed, max_cost_usd)
        # Without --arm, the RAGAS install and API key are checked before the database is opened.
        parts = ragas_metrics.build_parts(top_k) if arm is None else None
        with records.connect() as connection:
            if arm is not None:
                # Checked before any paid call: an arm without vectors would score as bad.
                embedding_experiment.require_embedded(connection, arm)
                embeddings = embedding_experiment.build_embeddings(embedding_experiment.ARMS[arm])
                parts = ragas_metrics.build_parts(top_k, embeddings=embeddings)
            assert parts is not None
            summary = ragas_metrics.run_ragas(
                items, parts, records.PostgresRunStore(connection), options
            )
    except (
        CaseFileError,
        FileNotFoundError,
        CalledProcessError,
        LLMConfigError,
        ragas_metrics.RagasNotInstalledError,
        embedding_experiment.ArmNotEmbeddedError,
        records.DatabaseNotConfiguredError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    means = ", ".join(
        f"{name} {'n/a' if value is None else f'{value:.3f}'}"
        for name, value in summary.means.items()
    )
    typer.echo(
        f"run {summary.run_id}: {summary.status.value}, {summary.cases_scored}/"
        f"{summary.cases_planned} items ({summary.cases_failed} failed), "
        f"${summary.cost_usd:.4f}, {summary.tokens} tokens; {means}"
    )


@eval_app.command("embeddings")
def eval_embeddings(
    arm: Annotated[
        list[str] | None,
        typer.Option(
            help=f"Arms to compare (repeatable): {' | '.join(embedding_experiment.ARMS)}"
            " [default: all]"
        ),
    ] = None,
    set_name: Annotated[
        list[embedding_experiment.ExperimentSet] | None,
        typer.Option("--set", help="Sets to search (repeatable) [default: both]"),
    ] = None,
    top_k: Annotated[
        int,
        typer.Option(min=1, max=embedding_experiment.SEARCH_DEPTH, help="Hits judged per query"),
    ] = embedding_experiment.DEFAULT_TOP_K,
    instruction: Annotated[
        str | None,
        typer.Option(help="Query instruction for the Qwen3 arms [default: the setting]"),
    ] = None,
    max_cost_usd: Annotated[
        float,
        typer.Option(
            min=0.000001,
            help="For the whole command: start no new query once this is spent (or a cost is"
            " unknown)",
        ),
    ] = embedding_experiment.DEFAULT_MAX_COST_USD,
) -> None:
    """Compare embedding arms by model-free context precision and recall on the Annex-matching
    and Q&A sets (X1a), one recorded run per arm and set. Costs only the query embeddings."""
    arms = arm or list(embedding_experiment.ARMS)
    unknown = sorted(set(arms) - set(embedding_experiment.ARMS))
    if unknown:
        typer.echo(f"Error: unknown --arm {', '.join(unknown)}", err=True)
        raise typer.Exit(code=2)
    sets = set_name or list(embedding_experiment.ExperimentSet)
    try:
        queries = {
            embedding_experiment.ExperimentSet.ANNEX_MATCH: embedding_experiment.annex_queries(
                load_cases(CaseSet.ANNEX_MATCH)
            ),
            embedding_experiment.ExperimentSet.QA: embedding_experiment.qa_queries(load_qa_items()),
        }
        git_sha, is_dirty = runner.current_git_state()
        options = embedding_experiment.ExperimentOptions(git_sha, is_dirty, top_k, max_cost_usd)
        with records.connect() as connection:
            for name in arms:
                embedding_experiment.require_embedded(connection, name)
            meter = UsageMeter()  # one cap for every run of the command
            for name, chosen in ((name, chosen) for name in arms for chosen in sets):
                if embedding_experiment.is_over_budget(meter, max_cost_usd):
                    # Checked before the run starts, so no empty eval_runs row is recorded.
                    typer.echo("Stopped: the cost cap is reached or a cost is unknown", err=True)
                    raise typer.Exit(code=1)
                summary = embedding_experiment.run_arm(
                    name,
                    chosen,
                    queries[chosen],
                    embedding_experiment.build_embeddings(
                        embedding_experiment.ARMS[name], instruction=instruction
                    ),
                    records.PostgresRunStore(connection),
                    options,
                    meter=meter,
                    connection=connection,
                )
                _echo_arm_summary(summary)
                if summary.status is runner.RunStatus.COST_CAP_REACHED:
                    typer.echo("Stopped: the cost cap is reached or a cost is unknown", err=True)
                    raise typer.Exit(code=1)
    except (
        CaseFileError,
        FileNotFoundError,
        CalledProcessError,
        LLMConfigError,
        embedding_experiment.ArmNotEmbeddedError,
        records.DatabaseNotConfiguredError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error


def _echo_arm_summary(summary: embedding_experiment.ArmSummary) -> None:
    means = ", ".join(
        f"{name} {'n/a' if value is None else f'{value:.3f}'}"
        for name, value in summary.means.items()
    )
    typer.echo(
        f"{summary.arm} {summary.experiment_set.value}: run {summary.run_id}, "
        f"{summary.status.value}, {summary.cases_scored}/{summary.cases_planned} "
        f"({summary.cases_failed} failed), ${summary.cost_usd:.6f}; {means}"
    )


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


@eval_app.command("tool-calls")
def eval_tool_calls(
    run_id: Annotated[UUID, typer.Argument(help="The eval_runs id whose traces to check")],
) -> None:
    """Print a stored run's tool-call correctness per step, from its LangSmith traces (V7)."""
    try:
        source = tool_calls.langsmith_source(get_settings())
        with records.connect() as connection:
            text = tool_calls.tool_call_report(connection, source, run_id)
    except (
        records.DatabaseNotConfiguredError,
        tool_calls.TracingNotConfiguredError,
        tool_calls.RunNotFoundError,
        tool_calls.NoLookupRunsError,
        tool_calls.TraceRecordError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    except LangSmithError as error:
        name = type(error).__name__
        typer.echo(f"Error: LangSmith error ({name}); check LANGSMITH_API_KEY", err=True)
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


@eval_app.command("similarity")
def eval_similarity(
    cases_dir: Annotated[Path, typer.Option(help="The case sets to check.")] = CASES_DIR,
    examples: Annotated[
        Path, typer.Option(help="The Commission example rows.")
    ] = eval_split.EXAMPLES_FILE,
    embeddings: Annotated[
        Path, typer.Option(help="The isolation vector cache the cosines come from.")
    ] = isolation.EMBEDDINGS_FILE,
    max_run: Annotated[
        int, typer.Option(min=1, help="A shared word run this long or longer fails a case.")
    ] = similarity.RUN_LIMIT,
    max_cosine: Annotated[
        float | None,
        typer.Option(
            min=-1, max=1, help="A cosine this high or higher fails a case [default: off]"
        ),
    ] = None,
) -> None:
    """Measure each case rewritten from a Commission example against its source: the longest
    shared word run and the embedding cosine (from the cached vectors; no paid call). Fails when a
    case reaches a limit."""
    try:
        results = similarity.check_similarity(cases_dir, examples, embeddings)
    except (
        CaseFileError,
        similarity.SimilarityError,
        isolation.IsolationFileError,
        FileNotFoundError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    limits = similarity.Limits(run=max_run, cosine=max_cosine)
    failed = 0
    for result in results:
        reasons = result.failures(limits)
        failed += bool(reasons)
        closeness = f"{result.cosine:.3f}" if result.cosine is not None else "-"
        if result.missing:
            closeness += f" ({'; '.join(result.missing)})"
        typer.echo(
            f"{'FAIL' if reasons else 'ok  '} {result.case_id} <- {result.source_example_id}  "
            f"run {result.run.length} ({result.run.part}), cosine {closeness}"
        )
        if reasons:
            typer.echo(f'     {"; ".join(reasons)}: "{" ".join(result.run.words)}"')
    missing = sum(result.cosine is None for result in results)
    summary = f"{len(results)} cases with a source example, {failed} too close"
    if missing:
        summary += f"; {missing} without a cosine"
    typer.echo(summary, err=bool(failed))
    if failed:
        raise typer.Exit(code=1)


@eval_app.command("isolation-embed")
def eval_isolation_embed(
    output: Annotated[
        Path, typer.Option(help="The benchmark-vector cache.")
    ] = isolation.EMBEDDINGS_FILE,
) -> None:
    """Embed the benchmark texts the isolation check compares with the corpus (Pile B examples,
    case descriptions and Q&A questions, not the appliedAI extraction) with the corpus arm, and
    write their vectors to eval/. Only texts missing from the cache are sent: a small paid call."""
    arm = corpus_embed_module.ARMS["qwen3"]
    dims = get_settings().embedding_dimensions
    try:
        texts = isolation.embedded_texts()
        cache = isolation.load_cache(output, arm.model, dims)
        embedder = OpenRouterEmbeddings(model=arm.model, provider=arm.provider, dimensions=dims)
        outcome = isolation.refresh_cache(cache, texts, embedder)
    except (
        LLMConfigError,
        EmbeddingError,
        CaseFileError,
        isolation.IsolationFileError,
        FileNotFoundError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    isolation.write_cache(outcome.cache, output)
    typer.echo(
        f"{len(texts)} texts: {outcome.embedded} embedded, {outcome.removed} removed; "
        f"{outcome.tokens} tokens, ${outcome.cost_usd:.6f}. Written: {output}"
    )


@eval_app.command("smoke")
def eval_smoke(
    model: Annotated[
        list[str] | None,
        typer.Option(help=f"One of: {', '.join(smoke.ARMS)}; repeat for both [default: both]"),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option(help="Print the probes and the cost estimate; make no call")
    ] = False,
    max_cost_usd: Annotated[
        float, typer.Option(min=0.000001, help="Per model: start no new batch once this is spent")
    ] = smoke.DEFAULT_MAX_COST_USD,
    concurrency: Annotated[
        int, typer.Option(min=1, max=runner.MAX_CONCURRENCY, help="Probes in flight at once")
    ] = smoke.DEFAULT_CONCURRENCY,
    node: Annotated[
        list[smoke.NodeName] | None,
        typer.Option(help="Probe only this node; repeat for several [default: X2's four]"),
    ] = None,
    case: Annotated[
        list[str] | None, typer.Option(help="Probe only this case id; repeat for several")
    ] = None,
) -> None:
    """The engine model smoke test (X2, decision 023): each model on the staged nodes and the
    approved own cases, stored in eval_runs, then decision 023's rule applied to the stored rows.
    `--node` and `--case` narrow the plan (X2b: the refused requests, decision 033)."""
    unknown = sorted(set(model or ()) - set(smoke.ARMS))
    if unknown:
        known = ", ".join(smoke.ARMS)
        typer.echo(f"Error: unknown model {', '.join(unknown)}; one of: {known}", err=True)
        raise typer.Exit(code=2)
    arms = [smoke.ARMS[name] for name in dict.fromkeys(model or smoke.ARMS)]
    nodes = tuple(dict.fromkeys(node)) if node else smoke.X2_NODES
    try:
        probes = smoke.plan_probes(nodes=nodes, case_ids=tuple(dict.fromkeys(case or ())))
    except (CaseFileError, smoke.UnknownCaseError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(smoke.format_plan(probes, arms))
    if dry_run:
        return
    try:
        git_state = runner.current_git_state()
        with records.connect() as connection:
            store = records.PostgresRunStore(connection)
            run_ids: dict[str, UUID] = {}
            for arm in arms:
                run = smoke.run_arm(
                    arm,
                    probes,
                    store,
                    get_settings(),
                    git_state,
                    max_cost_usd=max_cost_usd,
                    concurrency=concurrency,
                )
                run_ids[arm.name] = run.run_id
                typer.echo(
                    f"{arm.name}: run {run.run_id}, {run.status.value}, {run.probes_recorded}/"
                    f"{run.probes_planned} probes, ${run.cost_usd:.4f}, {run.tokens} tokens; "
                    f"{run.checked_late} checked late, {run.confirmed_late} confirmed"
                )
            if len(run_ids) == len(smoke.ARMS):
                typer.echo(_smoke_comparison(connection, run_ids))
    except (
        LLMConfigError,
        records.DatabaseNotConfiguredError,
        CalledProcessError,
        smoke_verdict.SmokeRunError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    if git_state[1]:
        typer.echo("Warning: uncommitted changes; the recorded git_sha may not reproduce", err=True)


@eval_app.command("smoke-compare")
def eval_smoke_compare(
    luna_run: Annotated[UUID, typer.Argument(help="The Luna smoke run's eval_runs id")],
    gemini_run: Annotated[UUID, typer.Argument(help="The Gemini smoke run's eval_runs id")],
) -> None:
    """Apply decision 023's rule to two stored smoke runs and print the table (read-only)."""
    try:
        with records.connect() as connection:
            text = _smoke_comparison(connection, {"luna": luna_run, "gemini": gemini_run})
    except (records.DatabaseNotConfiguredError, smoke_verdict.SmokeRunError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(text)


@eval_app.command("smoke-recheck")
def eval_smoke_recheck(
    run_ids: Annotated[list[UUID], typer.Argument(help="Stored smoke runs' eval_runs ids")],
    dry_run: Annotated[
        bool, typer.Option(help="Look the records up and print what would change; write nothing")
    ] = False,
) -> None:
    """Look up again the generation records of stored smoke probes that failed only because the
    record wasn't found in time, rescore the confirmed ones from their stored replies, and print
    the comparison (X2, decision 023 addendum). Makes no model call."""
    try:
        verify = GenerationLookup(get_settings()).served_by_all
        with (
            records.connect() as connection,
            connection.transaction(force_rollback=True) if dry_run else nullcontext(),
        ):
            _recheck_and_compare(connection, list(dict.fromkeys(run_ids)), verify)
    except (
        LLMConfigError,
        records.DatabaseNotConfiguredError,
        smoke_verdict.SmokeRunError,
        smoke_recheck.RecheckError,
        CaseFileError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    if dry_run:
        typer.echo("Dry run: nothing was written; the comparison shows the rows as they would be.")


def _recheck_and_compare(
    connection: psycopg.Connection, run_ids: list[UUID], verify: VerifyAll
) -> None:
    """Every run is read and checked first, so a run that can't be rechecked stops the command
    before anything is written; then each run's summary is printed as soon as it is stored."""
    prepared = [smoke_recheck.prepare_run(connection, run_id) for run_id in run_ids]
    rechecks: list[smoke_recheck.RunRecheck] = []
    for run in prepared:
        recheck = smoke_recheck.apply_recheck(connection, run, verify)
        rechecks.append(recheck)
        typer.echo(smoke_recheck.format_recheck(recheck) + "\n")
    pair = smoke_recheck.comparison_pair(rechecks)
    if pair is None:
        typer.echo("No comparison: give one luna and one gemini run.")
    else:
        typer.echo(_smoke_comparison(connection, pair))


@eval_app.command("smoke-refusals")
def eval_smoke_refusals(
    engine_run: Annotated[
        list[UUID], typer.Option(help="A stored Luna smoke run's id; repeat for several runs")
    ],
    second_run: Annotated[
        UUID, typer.Option(help="The second model's stored smoke run on the refused cases")
    ],
) -> None:
    """Apply decision 033's rule to stored smoke runs and print the table per node (X2b,
    read-only): does the second model answer what Luna's provider refused?"""
    try:
        with records.connect() as connection:
            table, runs = smoke_refusals.compare_stored(
                connection, list(dict.fromkeys(engine_run)), second_run
            )
    except (records.DatabaseNotConfiguredError, smoke_verdict.SmokeRunError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except psycopg.Error as error:
        # A connection error's text can name the server; only the type is printed.
        typer.echo(f"Error: database error ({type(error).__name__}); check DATABASE_URL", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(smoke_refusals.format_table(table, runs))


def _smoke_comparison(connection: psycopg.Connection, run_ids: dict[str, UUID]) -> str:
    comparison = smoke_verdict.compare_runs(connection, run_ids)
    return smoke_verdict.format_comparison(comparison, run_ids)


@mcp_app.callback()
def mcp() -> None:
    """The MCP server for outside agents."""


@mcp_app.command("serve")
def mcp_serve() -> None:
    """Run the MCP server over stdio (for an MCP client or the MCP inspector)."""
    # Imported here: only this command needs the MCP SDK.
    from aiact.mcp.server import serve

    serve()


@api_app.callback()
def api() -> None:
    """The HTTP API the web app calls."""


@api_app.command("serve")
def api_serve() -> None:
    """Run the API on API_HOST:API_PORT (CORS for CORS_ORIGINS)."""
    # Imported here: only these commands need FastAPI and uvicorn.
    import uvicorn

    from aiact.api import create_app

    settings = get_settings()
    # Both proxy settings are passed, never uvicorn's defaults (which trust X-Forwarded-For
    # from 127.0.0.1 and would let a local peer pick the rate limit's key).
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        proxy_headers=settings.api_proxy_headers,
        forwarded_allow_ips=list(settings.api_forwarded_allow_ips),
    )


@api_app.command("openapi")
def api_openapi(
    check: Annotated[
        bool, typer.Option(help="Only check that the committed schema matches the app.")
    ] = False,
) -> None:
    """Export the API's OpenAPI schema to frontend/openapi.json (then run `pnpm gen:api`)."""
    from aiact.api import openapi

    if check:
        if not openapi.is_openapi_current():
            typer.echo(
                f"{openapi.OPENAPI_FILE} is stale: run `uv run aiact api openapi`.", err=True
            )
            raise typer.Exit(code=1)
        typer.echo(f"{openapi.OPENAPI_FILE} matches the app.")
        return
    changed = openapi.write_openapi()
    typer.echo(f"{'written' if changed else 'unchanged'}: {openapi.OPENAPI_FILE}")


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
FrontendLockOption = typer.Option(
    deps.FRONTEND_LOCK_PATH, "--frontend-lock", help="The frontend's pnpm-lock.yaml to read."
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
    lock: Path = LockOption,
    output: Path = OutputOption,
    licences: Path = LicencesOption,
    frontend_lock: Path = FrontendLockOption,
) -> None:
    """Update the licence cache (installed metadata, else PyPI or npm) and write DEPENDENCIES.md."""
    is_changed = _or_exit(
        lambda: deps.generate(lock, output, licences, frontend_lock_path=frontend_lock)
    )
    typer.echo(f"{'Updated' if is_changed else 'Unchanged'}: {output}")


@deps_app.command("check")
def deps_check(
    lock: Path = LockOption,
    output: Path = OutputOption,
    licences: Path = LicencesOption,
    frontend_lock: Path = FrontendLockOption,
) -> None:
    """Exit non-zero when docs/DEPENDENCIES.md or the licence cache is stale. Works offline."""
    result = _or_exit(lambda: deps.check(lock, output, licences, frontend_lock))
    typer.echo(result.message, err=not result.is_fresh)
    if not result.is_fresh:
        raise typer.Exit(code=1)
