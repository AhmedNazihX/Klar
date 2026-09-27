"""Generate and check `docs/DEPENDENCIES.md`, the dependency manifest (`aiact deps generate|check`).

Versions and the dependency graph come from `backend/uv.lock`. Licence and summary come from the
installed package metadata, or `unknown` when a package isn't installed here (for example a
Windows-only package on macOS). The output is deterministic: sorted rows, no timestamps.

The document is a header plus one section per lockfile. Only the Python section exists now; the
frontend story (P4) adds its own section from the pnpm lockfile through `render_document`.
"""

import difflib
import re
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from email.message import Message
from functools import cache
from importlib import metadata
from pathlib import Path

from aiact.settings import BACKEND_DIR

REPO_ROOT = BACKEND_DIR.parent
LOCK_PATH = BACKEND_DIR / "uv.lock"
OUTPUT_PATH = REPO_ROOT / "docs" / "DEPENDENCIES.md"
GENERATE_COMMAND = "uv run --project backend aiact deps generate"
CHECK_COMMAND = "uv run --project backend aiact deps check"

UNKNOWN = "unknown"
RUNTIME_GROUP = "runtime"
MAX_CELL_LENGTH = 80
MAX_DIFF_LINES = 20


@dataclass(frozen=True)
class PackageInfo:
    """What the installed metadata says about a package."""

    licence: str
    summary: str


@dataclass(frozen=True)
class Edge:
    """A dependency on `name`, with the extras it asks for."""

    name: str
    extras: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DirectDep:
    """A dependency the project declares itself, in its runtime set or a dependency group."""

    name: str
    group: str
    constraint: str
    extras: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LockedPackage:
    """One package in the lockfile; a name locked at several versions (forks) is merged."""

    name: str
    versions: tuple[str, ...]
    edges: tuple[Edge, ...]
    optional: Mapping[str, tuple[Edge, ...]]


@dataclass(frozen=True)
class Lock:
    """The parsed lockfile: the project's direct deps and every locked package by name."""

    direct: tuple[DirectDep, ...]
    packages: Mapping[str, LockedPackage]


@dataclass(frozen=True)
class CheckResult:
    """Whether the manifest on disk matches a fresh render, and what to tell the user if not."""

    is_fresh: bool
    message: str


InfoLookup = Callable[[str], PackageInfo]


# --- Reading the lockfile ------------------------------------------------------------------


def load_lock(path: Path) -> Lock:
    """Parse a `uv.lock` file. Raises `FileNotFoundError` or `ValueError` with a clear message."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path} is not valid TOML: {error}") from error
    raw_packages = data.get("package", [])
    root = _find_root(raw_packages, path)
    packages = _merge_packages(p for p in raw_packages if p is not root)
    return Lock(direct=_direct_deps(root), packages=packages)


def _find_root(raw_packages: list[dict[str, object]], path: Path) -> dict[str, object]:
    """The project itself: the package whose source is the project directory."""
    for package in raw_packages:
        source = package.get("source")
        if isinstance(source, dict) and "." in (source.get("editable"), source.get("virtual")):
            return package
    raise ValueError(f"{path} has no project package (a source with editable or virtual = '.')")


def _direct_deps(root: Mapping[str, object]) -> tuple[DirectDep, ...]:
    meta = _as_dict(root.get("metadata"))
    groups: dict[str, object] = {RUNTIME_GROUP: meta.get("requires-dist", [])}
    groups.update(_as_dict(meta.get("requires-dev")))
    return tuple(
        DirectDep(
            name=str(entry["name"]),
            group=group,
            constraint=_constraint(entry),
            extras=_strings(entry.get("extras")),
        )
        for group, entries in groups.items()
        for entry in _as_list(entries)
    )


def _constraint(entry: Mapping[str, object]) -> str:
    specifier = str(entry.get("specifier") or "*")
    marker = entry.get("marker")
    return f"{specifier}; {marker}" if marker else specifier


def _merge_packages(raw_packages: Iterable[dict[str, object]]) -> dict[str, LockedPackage]:
    merged: dict[str, LockedPackage] = {}
    for raw in raw_packages:
        name = str(raw["name"])
        previous = merged.get(name, LockedPackage(name, (), (), {}))
        optional = {
            extra: _edges(entries)
            for extra, entries in _as_dict(raw.get("optional-dependencies")).items()
        }
        merged[name] = LockedPackage(
            name=name,
            versions=tuple(sorted({*previous.versions, str(raw.get("version", UNKNOWN))})),
            edges=tuple(dict.fromkeys((*previous.edges, *_edges(raw.get("dependencies", []))))),
            optional={**previous.optional, **optional},
        )
    return merged


def _edges(entries: object) -> tuple[Edge, ...]:
    return tuple(
        Edge(str(entry["name"]), _strings([entry["extra"]] if "extra" in entry else []))
        for entry in _as_list(entries)
    )


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _strings(value: object) -> frozenset[str]:
    return frozenset(str(item) for item in value) if isinstance(value, list) else frozenset()


def _as_list(value: object) -> list[dict[str, object]]:
    return [entry for entry in value if isinstance(entry, dict)] if isinstance(value, list) else []


# --- The dependency graph ------------------------------------------------------------------


def closure(lock: Lock, start: Edge) -> frozenset[str]:
    """Every package name reachable from `start` (itself excluded), following requested extras."""
    seen: set[tuple[str, str]] = set()
    reached: set[str] = set()
    stack = [start]
    while stack:
        edge = stack.pop()
        package = lock.packages.get(edge.name)
        if package is None:
            continue
        for part in ("", *sorted(edge.extras)):
            if (edge.name, part) in seen:
                continue
            seen.add((edge.name, part))
            children = package.optional.get(part, ()) if part else package.edges
            reached.update(child.name for child in children)
            stack.extend(children)
    return frozenset(reached - {start.name})


def pulled_in_by(lock: Lock) -> dict[str, tuple[str, ...]]:
    """Map each transitive package (not declared directly) to the direct deps that pull it in."""
    direct_names = {dep.name for dep in lock.direct}
    owners: dict[str, set[str]] = {}
    for dep in lock.direct:
        for name in closure(lock, Edge(dep.name, dep.extras)) - direct_names:
            owners.setdefault(name, set()).add(dep.name)
    return {name: tuple(sorted(owners[name])) for name in sorted(owners)}


# --- Package metadata ----------------------------------------------------------------------


@cache
def installed_info(name: str) -> PackageInfo:
    """Licence and summary from the installed distribution, `unknown` when it isn't installed."""
    try:
        meta = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return PackageInfo(UNKNOWN, UNKNOWN)
    # `PackageMetadata` is a protocol; the object behind it is an `email.message.Message`.
    message = meta if isinstance(meta, Message) else Message()
    return PackageInfo(licence_of(message), _clean(message.get("Summary")) or UNKNOWN)


def licence_of(meta: Message) -> str:
    """`License-Expression`, then a short `License`, then `License ::` classifiers, else `unknown`.

    A long `License` field is usually the full licence text, so classifiers win over it; with no
    classifiers it is truncated to fit a table cell.
    """
    expression = _clean(meta.get("License-Expression"))
    if expression:
        return expression
    licence = _clean(meta.get("License"))
    classifiers = [
        entry.split("::")[-1].strip()
        for entry in meta.get_all("Classifier") or []
        if entry.startswith("License ::") and entry.split("::")[-1].strip() != "OSI Approved"
    ]
    if licence and (len(licence) <= MAX_CELL_LENGTH or not classifiers):
        return licence
    return ", ".join(sorted(set(classifiers))) or UNKNOWN


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip() if value else ""


# --- Rendering -----------------------------------------------------------------------------


def cell(value: str) -> str:
    """Make a value table-safe: one line, `|` escaped, truncated to `MAX_CELL_LENGTH`."""
    text = _clean(value) or UNKNOWN
    if len(text) > MAX_CELL_LENGTH:
        text = text[: MAX_CELL_LENGTH - 1].rstrip() + "…"
    return text.replace("|", "\\|")


def _table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + " --- |" * len(headers)]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return lines


def _group_order(group: str) -> tuple[bool, str]:
    return (group != RUNTIME_GROUP, group)


def render_python_section(lock: Lock, source_label: str, lookup: InfoLookup) -> str:
    """The backend section: a table of direct deps and a table of transitive packages."""

    def locked(name: str) -> str:
        package = lock.packages.get(name)
        return ", ".join(package.versions) if package else UNKNOWN

    direct = sorted(lock.direct, key=lambda dep: (_group_order(dep.group), dep.name))
    direct_rows = [
        (
            dep.name + (f"[{','.join(sorted(dep.extras))}]" if dep.extras else ""),
            dep.group,
            dep.constraint,
            locked(dep.name),
            lookup(dep.name).licence,
            lookup(dep.name).summary,
        )
        for dep in direct
    ]
    transitive_rows = [
        (name, locked(name), lookup(name).licence, ", ".join(owners))
        for name, owners in pulled_in_by(lock).items()
    ]
    lines = [
        "## Backend (Python)",
        "",
        f"Source: `{source_label}`.",
        "",
        "### Direct dependencies",
        "",
        *_table(("Package", "Group", "Constraint", "Locked", "Licence", "Summary"), direct_rows),
        "",
        "### Transitive packages",
        "",
        *_table(("Package", "Locked", "Licence", "Pulled in by"), transitive_rows),
    ]
    return "\n".join(lines)


def render_document(sections: Sequence[str]) -> str:
    """The whole manifest: the do-not-edit header, then each lockfile's section."""
    header = [
        "<!-- Generated file: do not edit by hand. -->",
        "# Dependencies",
        "",
        f"> Generated by `{GENERATE_COMMAND}`. Do not edit by hand.",
        "> The pre-commit hook regenerates it when `pyproject.toml` or `uv.lock` is committed,",
        f"> and `{CHECK_COMMAND}` fails when it is stale.",
        "> Licence and summary come from the installed package metadata; `unknown` means the",
        "> metadata was missing or the package isn't installed on the machine that generated it.",
    ]
    return "\n\n".join(["\n".join(header), *sections]) + "\n"


def render(lock_path: Path = LOCK_PATH, lookup: InfoLookup = installed_info) -> str:
    """Render the full manifest from a lockfile."""
    section = render_python_section(load_lock(lock_path), _label(lock_path), lookup)
    return render_document([section])


def _label(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(REPO_ROOT).as_posix()
        if resolved.is_relative_to(REPO_ROOT)
        else path.name
    )


# --- Commands ------------------------------------------------------------------------------


def generate(
    lock_path: Path = LOCK_PATH,
    output_path: Path = OUTPUT_PATH,
    lookup: InfoLookup = installed_info,
) -> bool:
    """Write the manifest. Returns whether the file changed."""
    content = render(lock_path, lookup)
    if output_path.exists() and output_path.read_text(encoding="utf-8") == content:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8", newline="\n")
    return True


def check(
    lock_path: Path = LOCK_PATH,
    output_path: Path = OUTPUT_PATH,
    lookup: InfoLookup = installed_info,
) -> CheckResult:
    """Compare the manifest on disk with a fresh render."""
    label = _label(output_path)
    fix = f"Run `{GENERATE_COMMAND}` and commit {label}."
    expected = render(lock_path, lookup)
    if not output_path.exists():
        return CheckResult(False, f"{label} does not exist. {fix}")
    actual = output_path.read_text(encoding="utf-8")
    if actual == expected:
        return CheckResult(True, f"{label} is up to date with {_label(lock_path)}.")
    diff = list(
        difflib.unified_diff(
            actual.splitlines(), expected.splitlines(), "on disk", "expected", lineterm="", n=0
        )
    )
    shown = diff[:MAX_DIFF_LINES] + (["…"] if len(diff) > MAX_DIFF_LINES else [])
    return CheckResult(
        False,
        f"{label} is out of date with {_label(lock_path)}. {fix}\n" + "\n".join(shown),
    )
