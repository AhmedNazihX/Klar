"""Exact references in a search query (X1b): "Article 50", "Art. 6(3)", "Annex III point 5(b)",
"recital 27", and the German forms "Artikel 26 Absatz 2", "Anhang III Nummer 4 Buchstabe a",
"Erwägungsgrund 27", read as provision ids (`art:50`, `art:6:3`, `annex:III:5:b`, …).

Search can't find these by itself: the meaning arm ranks "Article 50" by what the words mean,
not by the number, and the keyword arm drops "50" and "article" as too common (C8). So the ids
named here are looked up by id and put first (`search_ai_act`). An id the corpus doesn't have
(say "Article 500") simply finds nothing. Patterns of both languages apply to every query, as
a German question may well write "Art. 50".

A whole annex ("Annex III" alone) is not taken as a reference: questions name it as a category
("our Annex III system", "Hochrisiko-Systeme nach Anhang III"), and pinning its whole text, all
its points in one row, first would crowd out the point that answers them (X1b measured this on
four Q&A items). `get_provision` returns a whole annex when one is wanted.

A reference to another act is not one to the AI Act: "Article 22 GDPR", "Art. 17 DSGVO",
"Article 101 of the Treaty", "Article 6 of Regulation (EU) 2016/679", "GDPR Article 22". The
rule is simple and only looks next to the reference: it is skipped when another act's name
(`OTHER_ACT`) follows it straight away (after "of (the)", "der", "des", or a German "lit." or
"Satz" part) or stands straight before it. An act named elsewhere in the query leaves it be.
"""

import re
from collections.abc import Iterator

ARTICLE = re.compile(
    r"\b(?:articles?|artikel|art\.)\s*(?P<number>\d{1,3}[a-z]?)\b"
    r"(?:\s*\((?P<paragraph>\d{1,2}[a-z]?)\))?"
    r"(?:\s*\((?P<point>[a-z]{1,2})\))?"
    r"(?:\s*(?:abs\.|absatz)\s*(?P<absatz>\d{1,2}[a-z]?)\b)?"
    r"(?:\s*(?P<unterabsatz>unterabs\.|unterabsatz)\s*\d{1,2}\b)?"
    r"(?:\s*(?:buchst\.|buchstabe)\s*(?P<buchstabe>[a-z]{1,2})\b)?",
    re.IGNORECASE,
)
"""An article, with its paragraph and point in brackets (EN, and German citing that way) or
as Absatz and Buchstabe (DE). With a German Unterabsatz the reference stops at the paragraph:
the ids put a point under `sub<n>` only where a list restarts (C1), which a citation can't tell."""

ANNEX = re.compile(
    r"\b(?:annex|anhang)\s+(?P<annex>[IVXL]{1,5})\b"
    r"(?:,?\s*(?:section|abschnitt)\s+(?P<section>[A-Z])\b)?"
    r"(?:,?\s*(?:point|points|nummer|nr\.|ziffer)\s*(?P<point>\d{1,2})\b)?"
    r"(?:\s*\((?P<letter>[a-z])\)|\s*(?:buchst\.|buchstabe)\s*(?P<buchstabe>[a-z])\b)?",
    re.IGNORECASE,
)
"""An annex section or point, with its letter where given ("Annex I, Section A, point 11",
"Annex III point 5(b)", "Anhang III Nr. 5 Buchstabe b")."""

RECITAL = re.compile(
    r"\b(?:recitals?|erwägungsgr(?:und|ünde))\s+(?P<number>\d{1,3})\b", re.IGNORECASE
)

AI_ACT_NUMBER = "2024/1689"

OTHER_ACT = (
    r"(?:gdpr|ds-?gvo|tfeu|aeuv|teu|euv|charter|charta|treaty|vertrag\w*"
    r"|general\s+data\s+protection\s+regulation|datenschutz-grundverordnung"
    r"|(?:regulation|verordnung)\s*\((?:eu|ec|eg|eec|ewg)\)\s*(?:no\.?\s*|nr\.?\s*)?"
    rf"(?!{AI_ACT_NUMBER}\b)\d{{1,4}}/\d{{1,4}}"
    r"|directive|richtlinie)\b"
)
"""Another act a provision number may belong to: the GDPR, the Treaties and the Charter by
name, any Union regulation by number but the AI Act's own, and any directive."""

OTHER_ACT_AFTER = re.compile(
    r"(?:\s*(?:lit\.|litera|satz|s\.|uabs\.)\s*\w{1,3}\b)*"
    r"\s*,?\s*(?:of\s+(?:the\s+)?|der\s+|des\s+)?" + OTHER_ACT,
    re.IGNORECASE,
)
OTHER_ACT_BEFORE = re.compile(OTHER_ACT + r"(?:'s)?\s*$", re.IGNORECASE)


def exact_references(query: str) -> tuple[str, ...]:
    """The provision ids `query` names, in the order it names them, each once."""
    found = sorted(_matches(query))
    return tuple(dict.fromkeys(provision_id for _, provision_id in found))


def _matches(query: str) -> Iterator[tuple[int, str]]:
    """(position, provision id) for every reference to the AI Act in `query`."""
    return (
        (start, provision_id)
        for start, end, provision_id in _candidates(query)
        if not _names_another_act(query, start, end)
    )


def _names_another_act(query: str, start: int, end: int) -> bool:
    """Another act is named right after or right before `query[start:end]`."""
    return bool(OTHER_ACT_AFTER.match(query, end) or OTHER_ACT_BEFORE.search(query, 0, start))


def _candidates(query: str) -> Iterator[tuple[int, int, str]]:
    """(start, end, provision id) for every reference in `query`, whatever act it is in."""
    for match in ARTICLE.finditer(query):
        paragraph = match["paragraph"] or match["absatz"]
        point = None if match["unterabsatz"] else match["point"] or match["buchstabe"]
        yield (
            match.start(),
            match.end(),
            _join("art", [_lower(match["number"]), _lower(paragraph), _lower(point)]),
        )
    for match in ANNEX.finditer(query):
        if not (match["section"] or match["point"]):
            continue  # a whole annex: see the module docstring
        letter = match["letter"] or match["buchstabe"]
        sections = [match["section"].upper()] if match["section"] else []
        parts = [match["annex"].upper(), *sections, match["point"], _lower(letter)]
        yield match.start(), match.end(), _join("annex", parts)
    for match in RECITAL.finditer(query):
        yield match.start(), match.end(), f"recital:{match['number']}"


def _lower(value: str | None) -> str | None:
    return value.lower() if value else None


def _join(kind: str, parts: list[str | None]) -> str:
    """`kind:part:part…` up to the first part not given (a point without its paragraph is no
    reference to a point)."""
    given: list[str] = []
    for part in parts:
        if part is None:
            break
        given.append(part)
    return ":".join([kind, *given])
