#!/usr/bin/env python3
"""Read and update docs/BACKLOG.md for the story skills (/status, /story-start, /story-finish).

Usage (from anywhere inside the repo):
  backlog.py status              ready / in progress / blocked / done, plus the critical path
  backlog.py show <ID>           print the story's full entry
  backlog.py deps <ID>           list unmet deps; exit 1 if any are unmet
  backlog.py info <ID>           JSON: id, title, slug, lane, type, deps, done
  backlog.py tick <ID> <note>    mark the story [x] and add an outcome note

Stories are lines like "- [ ] **F3 · Title** · Deps: F1 · Type: agent", followed by indented lines.
Dependency ranges such as "E2–E7" are expanded; "B5" matches the grouped entry "B5a–e".
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

STORY_RE = re.compile(r"^- \[( |x)\] \*\*(?P<id>[A-Z]\d+[a-z]?(?:–[a-z])?) · (?P<title>[^*]+)\*\*(?P<rest>.*)$")
ID_RE = re.compile(r"\b([A-Z])(\d+)([a-z]?)(?:\s*[–-]\s*(?:([A-Z])?(\d+))?([a-z])?)?")
# Keep in sync with `python3 ~/.claude/skills/work-breakdown/scripts/backlog.py graph` (computed from the Deps).
CRITICAL_PATH = ["F1", "B1", "B2", "B3", "C2", "C3", "C4", "C6", "E5", "E8", "E9", "E10", "V8", "V9", "W1", "W2", "W3"]


@dataclass
class Story:
    id: str
    title: str
    done: bool
    header: str
    body: list[str] = field(default_factory=list)
    line_no: int = 0

    def _field(self, name: str) -> str:
        m = re.search(rf"{name}:\s*([^·]+)", self.header)
        return m.group(1).strip() if m else ""

    @property
    def deps_text(self) -> str:
        return self._field("Deps")

    @property
    def type(self) -> str:
        return self._field("Type").split()[0].rstrip(",") if self._field("Type") else ""

    @property
    def sub_ids(self) -> list[str]:
        """Sub-stories of a grouped entry: 'B5a–e' has B5a … B5e. Empty for ordinary stories."""
        m = re.fullmatch(r"([A-Z]\d+)([a-z])–([a-z])", self.id)
        if not m:
            return []
        return [m.group(1) + chr(c) for c in range(ord(m.group(2)), ord(m.group(3)) + 1)]

    @property
    def keys(self) -> list[str]:
        """IDs this entry answers to: 'B5a–e' answers to B5a–e itself, B5, and B5a … B5e."""
        if not self.sub_ids:
            return [self.id]
        return [self.id, self.sub_ids[0][:-1], *self.sub_ids]

    @property
    def subs_done(self) -> set[str]:
        """Sub-stories that already have an '**Outcome (B5c):**' note."""
        return {m.group(1) for line in self.body if (m := re.search(r"\*\*Outcome \(([A-Z]\d+[a-z])\):\*\*", line))}

    def is_done(self, sid: str) -> bool:
        """A sub-story is done once its outcome note exists; the group or a plain story once ticked."""
        return self.done or (sid in self.sub_ids and sid in self.subs_done)

    @property
    def slug(self) -> str:
        words = re.sub(r"[^a-z0-9 ]+", " ", self.title.lower().replace("`", "")).split()
        stop = {"the", "a", "an", "and", "of", "for", "with", "into", "as", "in", "to", "one", "per"}
        return "-".join([w for w in words if w not in stop][:4]) or self.id.lower()

    @property
    def lane(self) -> str:
        if self.id == "C2":
            return "c2"
        if self.id == "B1" or re.fullmatch(r"C\d+", self.id):
            return "corpus"
        return "other"


def repo_root() -> Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def backlog_path() -> Path:
    return repo_root() / "docs" / "BACKLOG.md"


def load() -> tuple[list[str], list[Story]]:
    lines = backlog_path().read_text(encoding="utf-8").splitlines()
    stories: list[Story] = []
    current: Story | None = None
    for i, line in enumerate(lines):
        m = STORY_RE.match(line)
        if m:
            current = Story(m["id"], m["title"].strip(), line[3] == "x", line, line_no=i)
            stories.append(current)
        elif current and (line.startswith("  ") or line == ""):
            current.body.append(line)
        else:
            current = None
    return lines, stories


def parse_deps(text: str) -> tuple[list[str], list[str]]:
    """Return (story IDs, free-text conditions that can't be checked automatically)."""
    ids: list[str] = []
    notes: list[str] = []
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if part.startswith("–") or part.startswith("-"):
            remark = part.lstrip("–- ").strip("() ")
            if remark:
                notes.append(remark)  # "–" means no story deps; anything after it is a remark
            continue
        found = False
        for m in ID_RE.finditer(part):
            letter, start, suffix, end_letter, end, end_suffix = m.groups()
            found = True
            if end and (end_letter in (None, letter)):
                ids += [f"{letter}{n}" for n in range(int(start), int(end) + 1)]
            elif end_suffix and suffix:
                ids += [f"{letter}{start}{chr(c)}" for c in range(ord(suffix), ord(end_suffix) + 1)]
            else:
                ids.append(f"{letter}{start}{suffix}")
        if not found:
            notes.append(part)
    return list(dict.fromkeys(ids)), notes


def index(stories: list[Story]) -> dict[str, Story]:
    return {k: s for s in stories for k in s.keys}


def unmet(story: Story, by_id: dict[str, Story]) -> tuple[list[str], list[str]]:
    ids, notes = parse_deps(story.deps_text)
    missing = [i for i in ids if i in by_id and not by_id[i].is_done(i)]
    unknown = [i for i in ids if i not in by_id]
    return missing, notes + [f"unknown story {u}" for u in unknown]


def branches() -> set[str]:
    out = subprocess.run(["git", "branch", "--format=%(refname:short)"], capture_output=True, text=True)
    return set(out.stdout.split())


def find(stories: list[Story], sid: str) -> Story:
    by_id = index(stories)
    if sid not in by_id:
        sys.exit(f"No story {sid} in {backlog_path()}")
    return by_id[sid]


def cmd_status(stories: list[Story]) -> None:
    by_id = index(stories)
    live = branches()
    rows: dict[str, list[str]] = {"In progress": [], "Ready": [], "Blocked": [], "Done": []}
    for s in stories:
        in_progress = any(b.startswith(f"story/{k}-") for k in s.keys for b in live)
        missing, notes = unmet(s, by_id)
        label = f"{s.id} · {s.title}"
        if s.sub_ids and not s.done:
            left = [i for i in s.sub_ids if i not in s.subs_done]
            label += f"  (sub-stories left: {', '.join(left) or 'none, tick the group'})"
        if s.done:
            rows["Done"].append(label)
        elif in_progress:
            rows["In progress"].append(f"{label}  [{s.type}]")
        elif missing:
            rows["Blocked"].append(f"{label}  ← waiting on {', '.join(missing)}")
        else:
            extra = f"  (check: {'; '.join(notes)})" if notes else ""
            rows["Ready"].append(f"{label}  [{s.type}, lane {s.lane}]{extra}")
    done = sum(s.done for s in stories)
    print(f"Backlog: {done}/{len(stories)} stories done\n")
    for name, items in rows.items():
        if name == "Done":
            print(f"## Done ({len(items)})")
            print("  " + (", ".join(i.split(" · ")[0] for i in items) or "none"))
            print()
            continue
        print(f"## {name} ({len(items)})")
        for item in items:
            print(f"  - {item}")
        print()
    path = " → ".join(f"{i}✓" if by_id.get(i) and by_id[i].done else i for i in CRITICAL_PATH)
    nxt = next((i for i in CRITICAL_PATH if i in by_id and not by_id[i].done), None)
    print(f"## Critical path\n  {path}\n  next on the path: {nxt or 'complete'}")


def cmd_tick(lines: list[str], story: Story, sid: str, note: str) -> None:
    """Tick a story. For a sub-story of a grouped entry (B5c of B5a–e), only add a note:
    the group's box is ticked with `tick B5` once every sub-story is done."""
    sub = sid in story.sub_ids
    if story.done:
        sys.exit(f"{story.id} is already ticked")
    if sub and sid in story.subs_done:
        sys.exit(f"{sid} already has an outcome note")
    if not sub and story.sub_ids:
        left = [i for i in story.sub_ids if i not in story.subs_done]
        if left:
            sys.exit(f"Can't tick {story.id}: sub-stories without an outcome note: {', '.join(left)}")
    if not sub:
        lines[story.line_no] = lines[story.line_no].replace("- [ ]", "- [x]", 1)
    last = story.line_no + len(story.body)
    while last > story.line_no and lines[last].strip() == "":
        last -= 1
    lines.insert(last + 1, f"  **Outcome{f' ({sid})' if sub else ''}:** {note}")
    backlog_path().write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Added the outcome note for {sid}." if sub else f"Ticked {story.id} and added the outcome note.")


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    lines, stories = load()
    cmd, *args = argv
    if cmd == "status":
        cmd_status(stories)
    elif cmd == "show":
        s = find(stories, args[0])
        print("\n".join([s.header, *s.body]).rstrip())
    elif cmd == "deps":
        s = find(stories, args[0])
        missing, notes = unmet(s, index(stories))
        for m in missing:
            print(f"unmet: {m} · {index(stories)[m].title}")
        for n in notes:
            print(f"check by hand: {n}")
        sys.exit(1 if missing else 0)
    elif cmd == "info":
        s = find(stories, args[0])
        ids, notes = parse_deps(s.deps_text)
        # branch_id is what goes into the branch name: the requested ID (B5c), never the group ID (B5a–e).
        info = {"id": s.id, "branch_id": args[0], "title": s.title, "slug": s.slug, "lane": s.lane,
                "type": s.type, "deps": ids, "dep_notes": notes, "done": s.is_done(args[0]),
                "sub_stories": s.sub_ids}
        print(json.dumps(info, ensure_ascii=False))
    elif cmd == "tick":
        cmd_tick(lines, find(stories, args[0]), args[0], " ".join(args[1:]) or "done")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
