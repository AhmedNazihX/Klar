"""Read the amending instructions of the Digital Omnibus: which AI Act provisions change, and when.

An amending article reads `Regulation (EU) 2024/1689 is amended as follows:` and lists numbered
instructions; an instruction that is itself `amended as follows:` lists lettered sub-instructions.
Every leaf instruction becomes an `Amendment`:
- `action`: replace, insert, add, delete or amend, from the verb of the instruction;
- `targets`: the AI Act provision ids it touches. For a replacement or deletion, that's the
  provision the instruction names (`in Article 50, paragraph 7 is replaced` → `art:50:7`). For an
  insertion, it's the new provisions, read from the labels of the quoted text (`the following
  points are inserted: '(ba) ... (bb) ...` → `art:5:1:ba`, `art:5:1:bb`);
- `in_force_from`: when the change takes effect, the act's entry into force (the Official Journal
  date plus the day count in its final article: the Omnibus is 24.7.2026 + 3 days);
- `dates`: every date the instruction's text mentions, such as a deferred application date or a
  grace period (`… comply with Article 50(2) by 2 December 2026`).

The instructions are worded differently in each language (`paragraph 2 is replaced` vs `Absatz 2
erhält folgende Fassung`), so each language has its own patterns. Targets are then checked against
the AI Act's provision ids of the same language: where German counts an unnumbered paragraph
(`Artikel 113 Absatz 3`) the paragraph level doesn't exist and is dropped, so both languages
resolve to the same ids.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from lxml.html import HtmlElement
from pydantic import BaseModel, ConfigDict

from aiact.corpus.eurlex_html import (
    PARAGRAPH_PREFIX_RE,
    QUOTES,
    Block,
    Item,
    Text,
    element_text,
    render,
)
from aiact.corpus.sources import Language

AmendmentAction = Literal["replace", "insert", "add", "delete", "amend"]

AI_ACT_NUMBER = "2024/1689"
"""How the amending acts name the AI Act."""


class Amendment(BaseModel):
    """What one amending instruction changes in the AI Act."""

    model_config = ConfigDict(frozen=True)

    action: AmendmentAction
    targets: tuple[str, ...]
    """AI Act provision ids that are replaced, deleted or amended, or that are new."""
    in_force_from: date | None
    """The amending act's entry into force: the day the new text takes effect."""
    dates: tuple[date, ...] = ()
    """Every date the instruction mentions (deferred application, deadlines), sorted."""


@dataclass(frozen=True)
class _Patterns:
    """The wording of amending instructions in one language."""

    group: re.Pattern[str]
    article: re.Pattern[str]
    annex: re.Pattern[str]
    section: re.Pattern[str]
    paragraph: re.Pattern[str]
    point: re.Pattern[str]
    point_value: re.Pattern[str]
    noun: re.Pattern[str]
    nouns: dict[str, str]
    actions: tuple[tuple[str, AmendmentAction], ...]
    new_article: re.Pattern[str]
    new_annex: re.Pattern[str]
    date: re.Pattern[str]
    """A date, unless it's the date of a cited act (`Regulation … of 25 October 2012`)."""
    months: dict[str, int]
    publication_days: re.Pattern[str]
    ordinals: dict[str, int]


EN_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August")
EN_MONTHS += ("September", "October", "November", "December")
DE_MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August")
DE_MONTHS += ("September", "Oktober", "November", "Dezember")

PATTERNS: dict[Language, _Patterns] = {
    "en": _Patterns(
        group=re.compile(r"amended as follows:$"),
        article=re.compile(r"\bArticles? (\d+[a-z]*)(?:\((\d+[a-z]*)\))?"),
        annex=re.compile(r"\bAnnex ([IVXL]+)\b"),
        section=re.compile(r"\b[Ss]ection ([A-Z0-9])\b"),
        paragraph=re.compile(r"\bparagraphs? (\d+[a-z]*(?:(?:,| and) \d+[a-z]*)*)"),
        point=re.compile(r"\bpoints? ((?:\(\w+\)|\d+[a-z]?)(?:(?:,| and) (?:\(\w+\)|\d+[a-z]?))*)"),
        point_value=re.compile(r"\((\w+)\)|(\d+[a-z]?)"),
        noun=re.compile(r"\bfollowing (\w+)"),
        nouns={
            "Article": "article",
            "article": "article",
            "Articles": "article",
            "articles": "article",
            "paragraph": "paragraph",
            "paragraphs": "paragraph",
            "point": "point",
            "points": "point",
            "Annex": "annex",
            "annex": "annex",
        },
        actions=(
            ("deleted", "delete"),
            ("inserted", "insert"),
            ("added", "add"),
            ("replaced", "replace"),
            ("amended", "amend"),
        ),
        new_article=re.compile(r"^Article (\d+[a-z]*)$"),
        new_annex=re.compile(r"^(?:Annex|ANNEX) ([IVXL]+)$"),
        date=re.compile(r"(?<!of )\b(\d{1,2}) (" + "|".join(EN_MONTHS) + r") (\d{4})\b"),
        months={name: i + 1 for i, name in enumerate(EN_MONTHS)},
        publication_days=re.compile(r"enter into force on the (\w+) day following"),
        ordinals={"third": 3, "twentieth": 20},
    ),
    "de": _Patterns(
        group=re.compile(r"wie folgt geändert:$"),
        article=re.compile(r"\bArtikel (\d+[a-z]*)"),
        annex=re.compile(r"\bAnhang ([IVXL]+)\b"),
        section=re.compile(r"\bAbschnitt ([A-Z0-9])\b"),
        paragraph=re.compile(r"\bAbs(?:atz|ätze) (\d+[a-z]*(?:(?:,| und) \d+[a-z]*)*)"),
        point=re.compile(
            r"\b(?:Buchstaben?|Nummern?) "
            r"((?:\d+[a-z]?|[a-z]{1,2})(?:(?:,| und) (?:\d+[a-z]?|[a-z]{1,2}))*)\b"
        ),
        point_value=re.compile(r"\b(\d+[a-z]?|[a-z]{1,2})\b"),
        noun=re.compile(r"\b[Ff]olgende[nrs]? (\w+)"),
        nouns={
            "Artikel": "article",
            "Absatz": "paragraph",
            "Absätze": "paragraph",
            "Buchstabe": "point",
            "Buchstaben": "point",
            "Nummer": "point",
            "Nummern": "point",
            "Anhang": "annex",
        },
        actions=(
            ("gestrichen", "delete"),
            ("eingefügt", "insert"),
            ("angefügt", "add"),
            ("hinzugefügt", "add"),
            ("Fassung", "replace"),
            ("geändert", "amend"),
        ),
        new_article=re.compile(r"^Artikel (\d+[a-z]*)$"),
        new_annex=re.compile(r"^(?:Anhang|ANHANG) ([IVXL]+)$"),
        date=re.compile(r"(?<!vom )\b(\d{1,2})\. (" + "|".join(DE_MONTHS) + r") (\d{4})\b"),
        months={name: i + 1 for i, name in enumerate(DE_MONTHS)},
        publication_days=re.compile(r"am (\w+) Tag nach ihrer Veröffentlichung"),
        ordinals={"dritten": 3, "zwanzigsten": 20},
    ),
}

OJ_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
PARAGRAPH_VALUE_RE = re.compile(r"\d+[a-z]*")


@dataclass(frozen=True)
class AmendingContext:
    """What an article amending the AI Act needs to turn its instructions into `Amendment`s."""

    language: Language
    known_ids: frozenset[str]
    """The AI Act's provision ids in this language; empty means targets aren't checked."""
    in_force_from: date | None


def is_instruction_group(first_text: str, blocks: tuple[Block, ...], language: Language) -> bool:
    """True if `blocks` list amending instructions rather than quoted replacement text.

    `Article 2 is amended as follows:` introduces sub-instructions; `point (14) is amended as
    follows: '(14) ...'` introduces quoted text, recognisable by the quote on its first label.
    """
    if not PATTERNS[language].group.search(first_text):
        return False
    return not any(isinstance(b, Item) and b.raw_label[:1] in QUOTES for b in blocks)


def amending_context(
    intro: str, language: Language, article: HtmlElement, known_ids: frozenset[str]
) -> AmendingContext | None:
    """A context if the article amends the AI Act (`Regulation (EU) 2024/1689 is amended…`)."""
    if AI_ACT_NUMBER not in intro or not PATTERNS[language].group.search(intro):
        return None
    return AmendingContext(language, known_ids, entry_into_force(article, language))


def entry_into_force(element: HtmlElement, language: Language) -> date | None:
    """The act's entry into force: its Official Journal date plus the days its last article says."""
    root = element.getroottree().getroot()
    header = root.find(".//p[@class='oj-hd-date']")
    published = _oj_date(element_text(header)) if header is not None else None
    patterns = PATTERNS[language]
    match = patterns.publication_days.search(element_text(root))
    days = patterns.ordinals.get(match.group(1)) if match else None
    if published is None or days is None:
        return None
    return published + timedelta(days=days)


def _oj_date(text: str) -> date | None:
    match = OJ_DATE_RE.match(text)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    return date(year, month, day)


@dataclass
class _Reference:
    """The provision an instruction chain points at, refined clause by clause."""

    article: str | None = None
    paragraphs: list[str] = field(default_factory=list)
    annex: str | None = None
    section: str | None = None
    points: list[str] = field(default_factory=list)

    def containers(self) -> list[list[str]]:
        """The id parts of each unit named above point level (`paragraphs 2 and 3` → two)."""
        if self.annex is not None:
            return [["annex", self.annex] + ([self.section] if self.section else [])]
        if self.article is None:
            return []
        return [["art", self.article, p] for p in self.paragraphs] or [["art", self.article]]


def _read_reference(chain: tuple[str, ...], patterns: _Patterns) -> _Reference:
    """Walk the instructions from the outermost in; each named unit narrows the reference."""
    ref = _Reference()
    for text in chain:
        events: list[tuple[int, str, re.Match[str]]] = []
        for kind in ("article", "annex", "section", "paragraph", "point"):
            pattern: re.Pattern[str] = getattr(patterns, kind)
            events.extend((m.start(), kind, m) for m in pattern.finditer(text))
        for _, kind, match in sorted(events, key=lambda e: e[0]):
            _apply(ref, kind, match, patterns)
    return ref


def _apply(ref: _Reference, kind: str, match: re.Match[str], patterns: _Patterns) -> None:
    if kind == "article":
        ref.article, ref.annex, ref.section, ref.points = match.group(1), None, None, []
        paragraph = match.group(2) if match.lastindex and match.lastindex >= 2 else None
        ref.paragraphs = [paragraph] if paragraph else []
    elif kind == "annex":
        ref.annex, ref.article, ref.section, ref.points = match.group(1), None, None, []
    elif kind == "section":
        ref.section, ref.points = match.group(1), []
    elif kind == "paragraph":
        ref.paragraphs, ref.points = PARAGRAPH_VALUE_RE.findall(match.group(1)), []
    else:
        values = patterns.point_value.finditer(match.group(1))
        ref.points = [next(g for g in value.groups() if g) for value in values]


def _action(text: str, patterns: _Patterns) -> AmendmentAction:
    for word, action in patterns.actions:
        if word in text:
            return action
    return "amend"


def _new_labels(noun: str | None, quoted: tuple[Block, ...], patterns: _Patterns) -> list[str]:
    """The labels an insertion creates, read from the first level of the quoted text."""
    labels: list[str] = []
    for block in quoted:
        if isinstance(block, Item):
            is_wanted = block.is_paragraph if noun == "paragraph" else noun == "point"
            if is_wanted and block.label is not None:
                labels.append(block.label)
            continue
        pattern = {
            "article": patterns.new_article,
            "annex": patterns.new_annex,
            "paragraph": PARAGRAPH_PREFIX_RE,
        }.get(noun or "")
        match = pattern.match(block.text.strip(QUOTES).strip()) if pattern else None
        if match:
            labels.append(match.group(1))
    return labels


def _fit(parts: list[str], known: frozenset[str]) -> str:
    """The id for `parts`, adjusted to one the AI Act has (see the module docstring)."""
    pid = ":".join(parts)
    if not known or pid in known:
        return pid
    if parts[0] == "art" and len(parts) >= 4:
        without_paragraph = ":".join(parts[:2] + parts[3:])
        if without_paragraph in known:
            return without_paragraph
    while len(parts) > 2 and ":".join(parts) not in known:
        parts = parts[:-1]
    return ":".join(parts)


def _targets(
    action: AmendmentAction,
    ref: _Reference,
    noun: str | None,
    quoted: tuple[Block, ...],
    ctx: AmendingContext,
) -> tuple[str, ...]:
    containers = ref.containers()
    if action in ("insert", "add"):
        new = _new_labels(noun, quoted, PATTERNS[ctx.language])
        if noun in ("article", "annex") and new:
            prefix = "art" if noun == "article" else "annex"
            return tuple(f"{prefix}:{label}" for label in new)
        if new and containers:
            base = containers[0] + (ref.points[:1] if noun == "point" else [])
            fitted = _fit(base, ctx.known_ids)
            return tuple(f"{fitted}:{label}" for label in new)
    targets = (
        _fit(container + ([point] if point else []), ctx.known_ids)
        for container in containers
        for point in (ref.points or [None])
    )
    return tuple(dict.fromkeys(targets))


def _dates(text: str, patterns: _Patterns) -> tuple[date, ...]:
    found = {
        date(int(year), patterns.months[month], int(day))
        for day, month, year in patterns.date.findall(text)
    }
    return tuple(sorted(found))


def amendment_for(
    ctx: AmendingContext, chain: tuple[str, ...], blocks: tuple[Block, ...]
) -> Amendment:
    """The `Amendment` of a leaf instruction; `chain` is its text and its parents', outer first."""
    patterns = PATTERNS[ctx.language]
    instruction = chain[-1] if chain else ""
    quoted = _quoted(blocks, instruction)
    noun_match = patterns.noun.search(instruction)
    noun = patterns.nouns.get(noun_match.group(1)) if noun_match else None
    action = _action(instruction, patterns)
    ref = _read_reference(chain, patterns)
    return Amendment(
        action=action,
        targets=_targets(action, ref, noun, quoted, ctx),
        in_force_from=ctx.in_force_from,
        dates=_dates(render(blocks), patterns),
    )


def _quoted(blocks: tuple[Block, ...], instruction: str) -> tuple[Block, ...]:
    """The blocks after the instruction line: the quoted text it inserts or substitutes."""
    for index, block in enumerate(blocks):
        if isinstance(block, Text) and block.text == instruction:
            return blocks[index + 1 :]
    return blocks
