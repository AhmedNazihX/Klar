"""The `aiact` command root. Scripts are subcommands per area: `aiact corpus …`, `aiact eval …`.

Each area adds its commands to its group here (for example `@corpus_app.command()`).
Help texts come from the callback docstrings.
"""

from collections.abc import Callable
from pathlib import Path

import typer

from aiact import deps

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


@eval_app.callback()
def eval_() -> None:
    """Benchmark split, runs and metrics."""


@deps_app.callback()
def deps_() -> None:
    """Generate and check docs/DEPENDENCIES.md from the lockfile."""


LockOption = typer.Option(deps.LOCK_PATH, "--lock", help="The uv.lock to read.")
OutputOption = typer.Option(deps.OUTPUT_PATH, "--output", help="The manifest to write or check.")


def _or_exit[T](action: Callable[[], T]) -> T:
    """Run a deps action; a missing or unreadable lockfile exits 2 with the reason."""
    try:
        return action()
    except (FileNotFoundError, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error


@deps_app.command("generate")
def deps_generate(lock: Path = LockOption, output: Path = OutputOption) -> None:
    """Write docs/DEPENDENCIES.md from uv.lock and the installed package metadata."""
    is_changed = _or_exit(lambda: deps.generate(lock, output))
    typer.echo(f"{'Updated' if is_changed else 'Unchanged'}: {output}")


@deps_app.command("check")
def deps_check(lock: Path = LockOption, output: Path = OutputOption) -> None:
    """Exit non-zero when docs/DEPENDENCIES.md is stale or missing."""
    result = _or_exit(lambda: deps.check(lock, output))
    typer.echo(result.message, err=not result.is_fresh)
    if not result.is_fresh:
        raise typer.Exit(code=1)
