"""Generate and check `docs/DEPENDENCIES.md`, the dependency manifest (`aiact deps generate|check`).

Versions and the dependency graph come from `backend/uv.lock` and `frontend/pnpm-lock.yaml`.
Licence and summary come from the committed cache `docs/dependency-licences.json`, keyed by
`name==version` (Python) and `npm:name==version` (frontend), so the manifest depends only on
committed files and renders the same on every platform. `generate` fills missing cache entries
from the installed metadata (when that exact version is installed) or else the PyPI JSON API or the
npm registry, writes `unknown` when both fail, and prunes entries no longer in a lock. `check`
never touches the network or the installed packages.

The document is a header plus one section per lockfile: the backend, then the frontend.
"""

import difflib
import glob
import json
import logging
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from email.message import Message
from importlib import metadata
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from aiact.settings import BACKEND_DIR

logger = logging.getLogger(__name__)

REPO_ROOT = BACKEND_DIR.parent
LOCK_PATH = BACKEND_DIR / "uv.lock"
FRONTEND_LOCK_PATH = REPO_ROOT / "frontend" / "pnpm-lock.yaml"
OUTPUT_PATH = REPO_ROOT / "docs" / "DEPENDENCIES.md"
LICENCES_PATH = REPO_ROOT / "docs" / "dependency-licences.json"
GENERATE_COMMAND = "uv run --project backend aiact deps generate"
CHECK_COMMAND = "uv run --project backend aiact deps check"
PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"
PYPI_TIMEOUT_SECONDS = 10
NPM_REGISTRY_URL = "https://registry.npmjs.org/{name}/{version}"
NPM_KEY_PREFIX = "npm:"
PYTHON_TITLE = "Backend (Python)"
FRONTEND_TITLE = "Frontend (JavaScript)"
# pnpm lockfile importer sections, and the group each one is shown as.
PNPM_GROUPS = {
    "dependencies": "runtime",
    "devDependencies": "dev",
    "optionalDependencies": "optional",
}

UNKNOWN = "unknown"
RUNTIME_GROUP = "runtime"
MAX_CELL_LENGTH = 80
MAX_DIFF_LINES = 20
MAX_NAMES_SHOWN = 10


class PackageInfo(BaseModel):
    """Licence and one-line summary of one package version, as stored in the licence cache."""

    model_config = ConfigDict(frozen=True)

    licence: str
    summary: str


UNKNOWN_INFO = PackageInfo(licence=UNKNOWN, summary=UNKNOWN)
LicenceCache = dict[str, PackageInfo]
InfoFetch = Callable[[str, str], PackageInfo | None]
_CACHE_ADAPTER = TypeAdapter(LicenceCache)


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
    # The version the project itself resolved (pnpm lists it per importer); `None` shows every
    # locked version of the name (uv forks).
    version: str | None = None


@dataclass(frozen=True)
class LockedPackage:
    """One package in the lockfile; a name locked at several versions (forks) is merged."""

    name: str
    versions: tuple[str, ...]
    edges: tuple[Edge, ...]
    optional: Mapping[str, tuple[Edge, ...]]


@dataclass(frozen=True)
class Lock:
    """The parsed lockfile: the project's direct deps and every locked package by name.

    `key_prefix` namespaces the lock's licence-cache keys (`npm:` for the frontend).
    """

    direct: tuple[DirectDep, ...]
    packages: Mapping[str, LockedPackage]
    key_prefix: str = ""


@dataclass(frozen=True)
class Section:
    """One lockfile in the manifest: the parsed lock, where it was read from, its title."""

    lock: Lock
    path: Path
    title: str


@dataclass(frozen=True)
class CheckResult:
    """Whether the manifest on disk matches a fresh render, and what to tell the user if not."""

    is_fresh: bool
    message: str


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
            edges=_union(previous.edges, _edges(raw.get("dependencies", []))),
            optional={
                extra: _union(previous.optional.get(extra, ()), optional.get(extra, ()))
                for extra in sorted({*previous.optional, *optional})
            },
        )
    return merged


def _union(first: tuple[Edge, ...], second: tuple[Edge, ...]) -> tuple[Edge, ...]:
    return tuple(dict.fromkeys((*first, *second)))


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


# --- Reading the pnpm lockfile (frontend) --------------------------------------------------


def load_pnpm_lock(path: Path) -> Lock:
    """Parse a `pnpm-lock.yaml` (v9) into a `Lock`. Raises `FileNotFoundError` or `ValueError`.

    pnpm can write a first YAML document for its own binary (`packageManagerDependencies`); only
    documents whose root importer declares dependencies describe the project.
    """
    try:
        documents = [_as_dict(doc) for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))]
    except yaml.YAMLError as error:
        raise ValueError(f"{path} is not valid YAML: {error}") from error
    projects = [doc for doc in documents if _pnpm_root(doc).keys() & PNPM_GROUPS.keys()]
    if not projects:
        raise ValueError(f"{path} has no project importer ('.') with dependencies")
    direct = tuple(dep for doc in projects for dep in _pnpm_direct(_pnpm_root(doc)))
    snapshots = [(key, _as_dict(value)) for doc in projects for key, value in _pnpm_snapshots(doc)]
    packages: dict[str, LockedPackage] = {}
    for key, snapshot in snapshots:
        name, version = _pnpm_name_version(key)
        edges = tuple(
            Edge(str(child))
            for section in ("dependencies", "optionalDependencies")
            for child in _as_dict(snapshot.get(section))
        )
        previous = packages.get(name, LockedPackage(name, (), (), {}))
        packages[name] = LockedPackage(
            name=name,
            versions=tuple(sorted({*previous.versions, version})),
            edges=_union(previous.edges, edges),
            optional={},
        )
    return Lock(direct=direct, packages=packages, key_prefix=NPM_KEY_PREFIX)


def _pnpm_root(document: Mapping[str, object]) -> dict[str, object]:
    return _as_dict(_as_dict(document.get("importers")).get("."))


def _pnpm_snapshots(document: Mapping[str, object]) -> list[tuple[str, object]]:
    return [(str(key), value) for key, value in _as_dict(document.get("snapshots")).items()]


def _pnpm_direct(root: Mapping[str, object]) -> list[DirectDep]:
    return [
        DirectDep(
            name=str(name),
            group=group,
            constraint=str(_as_dict(entry).get("specifier", "*")),
            version=str(_as_dict(entry).get("version", UNKNOWN)).split("(", 1)[0],
        )
        for section, group in PNPM_GROUPS.items()
        for name, entry in _as_dict(root.get(section)).items()
    ]


def _pnpm_name_version(key: str) -> tuple[str, str]:
    """`@scope/name@1.2.3(peer@4.5.6)` → (`@scope/name`, `1.2.3`): the peer suffix is dropped."""
    bare = key.split("(", 1)[0]
    at = bare.rfind("@")
    if at <= 0:
        raise ValueError(f"pnpm snapshot key {key!r} has no version")
    return bare[:at], bare[at + 1 :]


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


def installed_info(name: str, version: str) -> PackageInfo | None:
    """Licence and summary from the installed distribution, if exactly `version` is installed."""
    try:
        if metadata.version(name) != version:
            return None
        meta = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return None
    # `PackageMetadata` is a protocol; the object behind it is an `email.message.Message`.
    return _info_from(meta) if isinstance(meta, Message) else None


def pypi_info(name: str, version: str) -> PackageInfo | None:
    """Licence and summary from the PyPI JSON API, or `None` when PyPI can't be reached or read."""
    url = PYPI_URL.format(
        name=urllib.parse.quote(name, safe=""), version=urllib.parse.quote(version, safe="")
    )
    try:
        with urllib.request.urlopen(url, timeout=PYPI_TIMEOUT_SECONDS) as response:
            info = json.loads(response.read().decode("utf-8")).get("info")
    except (urllib.error.URLError, TimeoutError, ValueError, AttributeError) as error:
        logger.warning("PyPI lookup failed for %s==%s: %s", name, version, error)
        return None
    if not isinstance(info, dict):
        return None
    message = Message()
    for field, key in (("License-Expression", "license_expression"), ("License", "license")):
        if info.get(key):
            message[field] = str(info[key])
    for classifier in info.get("classifiers") or []:
        message["Classifier"] = str(classifier)
    if info.get("summary"):
        message["Summary"] = str(info["summary"])
    return _info_from(message)


def fetch_info(name: str, version: str) -> PackageInfo | None:
    """The installed metadata when that version is installed, else PyPI."""
    return installed_info(name, version) or pypi_info(name, version)


def _info_from(meta: Message) -> PackageInfo:
    return PackageInfo(licence=licence_of(meta), summary=_clean(meta.get("Summary")) or UNKNOWN)


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


# --- npm package metadata (frontend) -------------------------------------------------------


def npm_manifest_info(manifest: Mapping[str, object]) -> PackageInfo:
    """Licence and summary from a `package.json` or an npm registry version document."""
    summary = _clean(manifest.get("description")) or UNKNOWN
    return PackageInfo(licence=_npm_licence(manifest), summary=summary)


def _npm_licence(manifest: Mapping[str, object]) -> str:
    """`license` (a string, or an old `{type}` object), else the old `licenses` list."""
    licence = manifest.get("license")
    if isinstance(licence, dict):
        licence = _as_dict(licence).get("type")
    if licence:
        return _clean(licence)
    entries = manifest.get("licenses")
    types = [
        _clean(_as_dict(entry).get("type") if isinstance(entry, dict) else entry)
        for entry in (entries if isinstance(entries, list) else [])
    ]
    return " OR ".join(kind for kind in types if kind) or UNKNOWN


def installed_npm_info(node_modules: Path, name: str, version: str) -> PackageInfo | None:
    """From pnpm's store (`node_modules/.pnpm/<name>@<version>…`), if that version is installed."""
    folder = f"{glob.escape(name.replace('/', '+'))}@{glob.escape(version)}*"
    for candidate in sorted((node_modules / ".pnpm").glob(folder)):
        manifest = _read_json(candidate / "node_modules" / name / "package.json")
        if manifest.get("version") == version:
            return npm_manifest_info(manifest)
    return None


def npm_registry_info(name: str, version: str) -> PackageInfo | None:
    """From the npm registry, or `None` when it can't be reached or read."""
    url = NPM_REGISTRY_URL.format(
        name=urllib.parse.quote(name, safe="@/"), version=urllib.parse.quote(version, safe="")
    )
    try:
        with urllib.request.urlopen(url, timeout=PYPI_TIMEOUT_SECONDS) as response:
            manifest = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        logger.warning("npm registry lookup failed for %s@%s: %s", name, version, error)
        return None
    return npm_manifest_info(manifest) if isinstance(manifest, dict) else None


def npm_fetcher(node_modules: Path) -> InfoFetch:
    """An `InfoFetch` for npm packages: the installed `package.json`, else the registry."""

    def fetch(name: str, version: str) -> PackageInfo | None:
        return installed_npm_info(node_modules, name, version) or npm_registry_info(name, version)

    return fetch


def _read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return _as_dict(data)


# --- The licence cache ---------------------------------------------------------------------


def cache_key(name: str, version: str, prefix: str = "") -> str:
    return f"{prefix}{name}=={version}"


def _locked_pairs(lock: Lock) -> list[tuple[str, str]]:
    """Every (name, version) pair in the lock, sorted."""
    return sorted((p.name, v) for p in lock.packages.values() for v in p.versions)


def locked_keys(lock: Lock) -> set[str]:
    """The licence-cache key of every locked version."""
    return {cache_key(name, version, lock.key_prefix) for name, version in _locked_pairs(lock)}


def load_cache(path: Path) -> LicenceCache:
    """Read the licence cache; a missing file is an empty cache."""
    if not path.exists():
        return {}
    try:
        return _CACHE_ADAPTER.validate_json(path.read_bytes())
    except ValidationError as error:
        raise ValueError(f"{path} is not a valid licence cache: {error}") from error


def dump_cache(cache: Mapping[str, PackageInfo]) -> str:
    entries = {key: cache[key].model_dump() for key in sorted(cache)}
    return json.dumps(entries, indent=2, ensure_ascii=False) + "\n"


def fill_cache(lock: Lock, cache: Mapping[str, PackageInfo], fetch: InfoFetch) -> LicenceCache:
    """A cache of exactly the locked versions: kept entries, fetched missing ones, none stale."""
    keyed = [(cache_key(n, v, lock.key_prefix), n, v) for n, v in _locked_pairs(lock)]
    return {
        key: cache.get(key) or fetch(name, version) or UNKNOWN_INFO for key, name, version in keyed
    }


def _cache_mismatch(locks: Sequence[Lock], cache: Mapping[str, PackageInfo]) -> str:
    """Why the cache doesn't match the locks, or an empty string when it does."""
    expected = set[str]().union(*(locked_keys(lock) for lock in locks))
    problems = [
        f"{label}: {', '.join(keys[:MAX_NAMES_SHOWN])}{' …' if len(keys) > MAX_NAMES_SHOWN else ''}"
        for label, keys in (
            ("missing", sorted(expected - cache.keys())),
            ("stale", sorted(cache.keys() - expected)),
        )
        if keys
    ]
    return "; ".join(problems)


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


def _package_info(lock: Lock, cache: Mapping[str, PackageInfo], name: str) -> PackageInfo:
    """One row's info: each distinct licence across the locked versions, the last summary."""
    package = lock.packages.get(name)
    versions = package.versions if package else ()
    infos = [cache.get(cache_key(name, v, lock.key_prefix), UNKNOWN_INFO) for v in versions]
    if not infos:
        return UNKNOWN_INFO
    licences = dict.fromkeys(info.licence for info in infos)
    return PackageInfo(licence=" / ".join(licences), summary=infos[-1].summary)


def render_section(section: Section, cache: Mapping[str, PackageInfo]) -> str:
    """One lockfile's section: a table of direct deps and a table of transitive packages."""
    lock = section.lock

    def locked(name: str) -> str:
        package = lock.packages.get(name)
        return ", ".join(package.versions) if package else UNKNOWN

    def info(name: str) -> PackageInfo:
        return _package_info(lock, cache, name)

    def direct_info(dep: DirectDep) -> PackageInfo:
        if dep.version is None:
            return info(dep.name)
        return cache.get(cache_key(dep.name, dep.version, lock.key_prefix), UNKNOWN_INFO)

    direct = sorted(lock.direct, key=lambda dep: (_group_order(dep.group), dep.name))
    direct_rows = [
        (
            dep.name + (f"[{','.join(sorted(dep.extras))}]" if dep.extras else ""),
            dep.group,
            dep.constraint,
            dep.version or locked(dep.name),
            direct_info(dep).licence,
            direct_info(dep).summary,
        )
        for dep in direct
    ]
    transitive_rows = [
        (name, locked(name), info(name).licence, ", ".join(owners))
        for name, owners in pulled_in_by(lock).items()
    ]
    lines = [
        f"## {section.title}",
        "",
        f"Source: `{_label(section.path)}`.",
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
        "> The pre-commit hook regenerates it when `pyproject.toml`, `uv.lock`,",
        "> `frontend/package.json` or `frontend/pnpm-lock.yaml` is committed,",
        f"> and `{CHECK_COMMAND}` fails when it is stale.",
        "> Licence and summary come from `docs/dependency-licences.json`, filled from the",
        "> installed package metadata, PyPI or the npm registry; `unknown` means none had it.",
    ]
    return "\n\n".join(["\n".join(header), *sections]) + "\n"


def render(sections: Sequence[Section], cache: Mapping[str, PackageInfo]) -> str:
    """Render the full manifest from the parsed lockfiles and the licence cache."""
    return render_document([render_section(section, cache) for section in sections])


def _label(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(REPO_ROOT).as_posix()
        if resolved.is_relative_to(REPO_ROOT)
        else path.name
    )


# --- Commands ------------------------------------------------------------------------------


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def _sections(lock_path: Path, frontend_lock_path: Path | None) -> list[Section]:
    """The backend lock, then the frontend lock when one is given."""
    sections = [Section(load_lock(lock_path), lock_path, PYTHON_TITLE)]
    if frontend_lock_path is not None:
        frontend = load_pnpm_lock(frontend_lock_path)
        sections.append(Section(frontend, frontend_lock_path, FRONTEND_TITLE))
    return sections


def generate(
    lock_path: Path = LOCK_PATH,
    output_path: Path = OUTPUT_PATH,
    licences_path: Path = LICENCES_PATH,
    fetch: InfoFetch = fetch_info,
    frontend_lock_path: Path | None = FRONTEND_LOCK_PATH,
    npm_fetch: InfoFetch | None = None,
) -> bool:
    """Update the licence cache and write the manifest. Returns whether either file changed.

    `frontend_lock_path=None` renders the backend only (tests); it drops every `npm:` entry.
    `npm_fetch` defaults to the frontend's installed packages, else the npm registry.
    """
    sections = _sections(lock_path, frontend_lock_path)
    previous = load_cache(licences_path)
    cache: LicenceCache = {}
    for section in sections:
        section_fetch = fetch
        if section.lock.key_prefix == NPM_KEY_PREFIX:
            section_fetch = npm_fetch or npm_fetcher(section.path.parent / "node_modules")
        cache |= fill_cache(section.lock, previous, section_fetch)
    is_cache_changed = _write_if_changed(licences_path, dump_cache(cache))
    is_output_changed = _write_if_changed(output_path, render(sections, cache))
    return is_cache_changed or is_output_changed


def check(
    lock_path: Path = LOCK_PATH,
    output_path: Path = OUTPUT_PATH,
    licences_path: Path = LICENCES_PATH,
    frontend_lock_path: Path | None = FRONTEND_LOCK_PATH,
) -> CheckResult:
    """Compare the manifest on disk with a render from the locks and the cache. Offline."""
    label = _label(output_path)
    fix = f"Run `{GENERATE_COMMAND}` and commit {label} and {_label(licences_path)}."
    sections = _sections(lock_path, frontend_lock_path)
    locks_label = " and ".join(_label(section.path) for section in sections)
    cache = load_cache(licences_path)
    mismatch = _cache_mismatch([section.lock for section in sections], cache)
    if mismatch:
        return CheckResult(
            False, f"{_label(licences_path)} doesn't match {locks_label} ({mismatch}). {fix}"
        )
    if not output_path.exists():
        return CheckResult(False, f"{label} does not exist. {fix}")
    expected = render(sections, cache)
    actual = output_path.read_text(encoding="utf-8")
    if actual == expected:
        return CheckResult(True, f"{label} is up to date with {locks_label}.")
    diff = list(
        difflib.unified_diff(
            actual.splitlines(), expected.splitlines(), "on disk", "expected", lineterm="", n=0
        )
    )
    shown = diff[:MAX_DIFF_LINES] + (["…"] if len(diff) > MAX_DIFF_LINES else [])
    return CheckResult(
        False,
        f"{label} is out of date with {locks_label}. {fix}\n" + "\n".join(shown),
    )
