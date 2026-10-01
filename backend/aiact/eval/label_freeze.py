"""The label-freeze check (story B10a, decision 017): an approved case can't change unlogged.

How the check decides, in order:

- **Comparison base.** The caller names a git ref (`--base`, required). The check takes the merge
  base of that ref and `HEAD`, so a story branch is compared with the point it left main, not with
  whatever main has gained since. CI passes `origin/main` for pull requests and branch pushes, and
  the previous tip for a push to main (`.github/workflows/label-freeze.yml`).
- **Approved.** A case is approved when a `*.yaml` file under `eval/cases/` at the base holds it:
  decision 017 approves a category once its files are on main. The spot-check overrides in
  `eval/cases/academic_overrides.yaml` are approved the same way, keyed by the case id they
  override. A case id first seen after the base is new and needs no entry, whichever file holds it.
- **Changed.** Records are compared per id, as parsed YAML: an approved case whose record differs
  in any field (label, citation, description, notes, tags), or which is gone, has changed.
  Comments, formatting, key order and moves between files don't count. A change to the label
  itself (a case's `label`, `label_citation` or `as_of`; an override's `status`, `risk_class` or
  `label_citation`) or a removal is a *label change*.
- **A matching entry.** A row added to the table in `eval/LABEL_CHANGES.md` since the base. Its
  "Case id" cell names the case in one of two ways:
  - by id: full ids, where a bare number after an id reuses that id's prefix, so
    `academic-0160, 0253` names `academic-0160` and `academic-0253`;
  - by rule: a cell starting "<N> <prefix> cases" (`95 academic cases (by rule: …)`) covers the
    changed cases whose id starts with `<prefix>-` that no id names, but only when N (summed over
    every such row for the prefix) equals their number exactly, and never a label change: those
    always need an id row. A count that doesn't match fails the check and leaves them unlogged,
    so a bulk row can't absorb edits it doesn't declare.
- **The log is append-only.** A row present at the base must still be there, compared cell by
  cell after trimming (re-aligning the columns is fine); editing an old row would otherwise read
  as a new entry. A mistake in an old row is fixed with a new, corrective row.

The current side is the working tree, so uncommitted edits are checked too; in CI it equals `HEAD`.
"""

import re
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

import yaml

from aiact.settings import BACKEND_DIR

REPO_DIR = BACKEND_DIR.parent
CASES_PATH = PurePosixPath("eval/cases")
OVERRIDES_PATH = CASES_PATH / "academic_overrides.yaml"
LOG_PATH = PurePosixPath("eval/LABEL_CHANGES.md")

CASE_LABEL_FIELDS = frozenset({"label", "label_citation", "as_of"})
"""A case's `as_of` decides a date-dependent label, so editing it is a label change."""
OVERRIDE_LABEL_FIELDS = frozenset({"status", "risk_class", "label_citation"})
CASE_ID_CELL = 1
"""The log table's columns: Date | Case id | Old → new | Reason | Approved by."""
BULK_ROW = re.compile(r"^\s*(\d+)\s+([a-z0-9][a-z0-9_-]*)\s+cases?\b")
TOKEN_SEPARATORS = re.compile(r"[,;\s]+")
FULL_ID = re.compile(r"^[a-z0-9][a-z0-9_.:-]*-[a-z0-9_.:]+$")
SEPARATOR_CELL = re.compile(r"^:?-+:?$")


class FreezeCheckError(ValueError):
    """The check can't run: a git call failed or a case file can't be read."""


class RecordKind(StrEnum):
    CASE = "case"
    OVERRIDE = "override"


@dataclass(frozen=True)
class CaseKey:
    kind: RecordKind
    case_id: str


@dataclass(frozen=True)
class ChangedCase:
    key: CaseKey
    path: str
    """The file that held the case at the base."""
    is_removed: bool
    is_label_change: bool
    """The label itself changed, or the case is gone: only an id row covers it."""

    def describe(self) -> str:
        what = "removed" if self.is_removed else "changed"
        kind = "override for" if self.key.kind is RecordKind.OVERRIDE else "case"
        return f"{kind} {self.key.case_id} ({self.path}) {what}"


@dataclass(frozen=True)
class FreezeReport:
    base_sha: str
    changed: tuple[ChangedCase, ...]
    unlogged: tuple[ChangedCase, ...]
    edited_log_rows: tuple[str, ...]
    bulk_mismatches: tuple[str, ...]

    @property
    def is_ok(self) -> bool:
        return not self.unlogged and not self.edited_log_rows and not self.bulk_mismatches


@dataclass(frozen=True)
class LogCoverage:
    """What the log rows added since the base name: explicit ids and per-prefix bulk counts."""

    case_ids: frozenset[str]
    bulk_counts: Mapping[str, int]


LogRow = tuple[str, ...]
"""A table row as its trimmed cells."""


def check_label_freeze(base_ref: str, repo_dir: Path | None = None) -> FreezeReport:
    """Compare the approved cases at the merge base of `base_ref` and HEAD with the working tree
    of `repo_dir` (default: this repo)."""
    if not base_ref or base_ref.startswith("-"):
        raise FreezeCheckError(f"not a git ref: {base_ref!r}")
    repo_dir = repo_dir or REPO_DIR
    base_sha = _git(["merge-base", base_ref, "HEAD"], repo_dir).strip()
    base_records = _records(_files_at(base_sha, repo_dir))
    current_records = _records(_files_in_tree(repo_dir))
    changed = _changed_cases(base_records, current_records)
    base_rows = _log_rows(_file_at(base_sha, LOG_PATH, repo_dir) or "")
    current_rows = _log_rows(_read_text(repo_dir / LOG_PATH))
    edited = tuple((Counter(base_rows) - Counter(current_rows)).elements())
    added = tuple((Counter(current_rows) - Counter(base_rows)).elements())
    unlogged, mismatches = _unlogged(changed, _coverage(added))
    edited_text = tuple(f"| {' | '.join(row)} |" for row in edited)
    return FreezeReport(base_sha, changed, unlogged, edited_text, mismatches)


# --- reading the two sides ------------------------------------------------------------------------


def _files_at(sha: str, repo_dir: Path) -> dict[str, str]:
    """The case YAML files at `sha`, path → text."""
    listing = _git(["ls-tree", "-r", "-z", "--name-only", sha, "--", str(CASES_PATH)], repo_dir)
    paths = [path for path in listing.split("\0") if path.endswith(".yaml")]
    return {path: _file_at(sha, PurePosixPath(path), repo_dir) or "" for path in paths}


def _files_in_tree(repo_dir: Path) -> dict[str, str]:
    """The case YAML files in the working tree, path → text."""
    cases_dir = repo_dir / CASES_PATH
    if not cases_dir.is_dir():
        return {}
    return {
        path.relative_to(repo_dir).as_posix(): _read_text(path)
        for path in sorted(cases_dir.rglob("*.yaml"))
    }


def _file_at(sha: str, path: PurePosixPath, repo_dir: Path) -> str | None:
    """A file's text at `sha`, or None when it doesn't exist there."""
    completed = subprocess.run(
        ["git", "show", f"{sha}:{path}"], cwd=repo_dir, capture_output=True, text=True
    )
    return completed.stdout if completed.returncode == 0 else None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _git(arguments: list[str], repo_dir: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as exc:
        raise FreezeCheckError(f"git {' '.join(arguments)} failed: {exc.stderr.strip()}") from exc
    return completed.stdout


def _records(files: Mapping[str, str]) -> dict[CaseKey, tuple[str, object]]:
    """Every record by (kind, id), with the file that holds it."""
    records: dict[CaseKey, tuple[str, object]] = {}
    for path, text in files.items():
        kind = RecordKind.OVERRIDE if path == str(OVERRIDES_PATH) else RecordKind.CASE
        for case_id, record in _parse(path, text):
            key = CaseKey(kind, case_id)
            if key in records:
                raise FreezeCheckError(f"{path}: {kind} {case_id} also in {records[key][0]}")
            records[key] = (path, record)
    return records


def _parse(path: str, text: str) -> Iterable[tuple[str, object]]:
    try:
        document: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise FreezeCheckError(f"{path}: not valid YAML: {exc}") from exc
    if document is None:
        return ()
    items = document if isinstance(document, list) else [document]
    return tuple(_with_id(path, item) for item in items)


def _with_id(path: str, item: object) -> tuple[str, object]:
    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
        raise FreezeCheckError(f"{path}: every record needs a string id")
    return item["id"], item


# --- comparing ------------------------------------------------------------------------------------


def _changed_cases(
    base: Mapping[CaseKey, tuple[str, object]], current: Mapping[CaseKey, tuple[str, object]]
) -> tuple[ChangedCase, ...]:
    changed: list[ChangedCase] = []
    for key, (path, record) in sorted(base.items(), key=lambda item: item[1][0]):
        if key not in current:
            changed.append(ChangedCase(key, path, is_removed=True, is_label_change=True))
        elif current[key][1] != record:
            is_label_change = _is_label_change(key.kind, record, current[key][1])
            changed.append(ChangedCase(key, path, False, is_label_change))
    return tuple(changed)


def _is_label_change(kind: RecordKind, old: object, new: object) -> bool:
    fields = OVERRIDE_LABEL_FIELDS if kind is RecordKind.OVERRIDE else CASE_LABEL_FIELDS
    old_fields = old if isinstance(old, dict) else {}
    new_fields = new if isinstance(new, dict) else {}
    return any(old_fields.get(field) != new_fields.get(field) for field in fields)


def _log_rows(text: str) -> tuple[LogRow, ...]:
    """The table's data rows as trimmed cells; the header and the separator row are left out."""
    rows = (_cells(line) for line in text.splitlines() if line.lstrip().startswith("|"))
    return tuple(row for row in rows if not _is_header_or_separator(row))


def _cells(line: str) -> LogRow:
    return tuple(cell.strip() for cell in line.strip().strip("|").split("|"))


def _is_header_or_separator(cells: LogRow) -> bool:
    is_separator = all(SEPARATOR_CELL.match(cell) for cell in cells if cell)
    return is_separator or cells[:2] == ("Date", "Case id")


def _coverage(rows: Iterable[LogRow]) -> LogCoverage:
    case_ids: set[str] = set()
    bulk: Counter[str] = Counter()
    for cells in rows:
        cell = cells[CASE_ID_CELL] if len(cells) > CASE_ID_CELL else ""
        bulk_match = BULK_ROW.match(cell)
        if bulk_match:
            bulk[bulk_match.group(2)] += int(bulk_match.group(1))
        else:
            case_ids.update(_named_ids(cell))
    return LogCoverage(frozenset(case_ids), dict(bulk))


def _named_ids(cell: str) -> tuple[str, ...]:
    """Full ids, and bare numbers expanded with the prefix of the id before them."""
    names: list[str] = []
    prefix: str | None = None
    for token in TOKEN_SEPARATORS.split(cell.replace("`", "")):
        if FULL_ID.match(token):
            names.append(token)
            prefix = token.rsplit("-", 1)[0]
        elif token.isdigit() and prefix is not None:
            names.append(f"{prefix}-{token}")
    return tuple(names)


def _unlogged(
    changed: tuple[ChangedCase, ...], coverage: LogCoverage
) -> tuple[tuple[ChangedCase, ...], tuple[str, ...]]:
    """The changes no row covers, and the bulk counts that don't match exactly."""
    unnamed = [case for case in changed if case.key.case_id not in coverage.case_ids]
    covered: set[str] = set()
    mismatches: list[str] = []
    for prefix, count in sorted(coverage.bulk_counts.items()):
        ids = {
            case.key.case_id
            for case in unnamed
            if case.key.case_id.startswith(f"{prefix}-") and not case.is_label_change
        }
        if len(ids) == count:
            covered |= ids
        else:
            mismatches.append(
                f"bulk rows declare {count} {prefix} cases, but {len(ids)} changed {prefix} "
                "cases (label changes aside) match no id row"
            )
    unlogged = tuple(case for case in unnamed if case.key.case_id not in covered)
    return unlogged, tuple(mismatches)
