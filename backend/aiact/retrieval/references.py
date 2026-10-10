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
"""

import re
from collections.abc import Iterator

ARTICLE = re.compile(
    r"\b(?:articles?|artikel|art\.)\s*(?P<number>\d{1,3}[a-z]?)\b"
    r"(?:\s*\((?P<paragraph>\d{1,2}[a-z]?)\))?"
    r"(?:\s*\((?P<point>[a-z]{1,2})\))?"
    r"(?:\s*(?:abs\.|absatz)\s*(?P<absatz>\d{1,2}[a-z]?)\b)?"
    r"(?:\s*(?:unterabs\.|unterabsatz)\s*\d{1,2}\b)?"
    r"(?:\s*(?:buchst\.|buchstabe)\s*(?P<buchstabe>[a-z]{1,2})\b)?",
    re.IGNORECASE,
)
"""An article, with its paragraph and point in brackets (EN, and German citing that way) or
as Absatz and Buchstabe (DE). A German Unterabsatz is skipped: ids number no subparagraphs."""

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


def exact_references(query: str) -> tuple[str, ...]:
    """The provision ids `query` names, in the order it names them, each once."""
    found = sorted(_matches(query))
    return tuple(dict.fromkeys(provision_id for _, provision_id in found))


def _matches(query: str) -> Iterator[tuple[int, str]]:
    """(position, provision id) for every reference in `query`."""
    for match in ARTICLE.finditer(query):
        paragraph = match["paragraph"] or match["absatz"]
        point = match["point"] or match["buchstabe"]
        yield (
            match.start(),
            _join("art", [_lower(match["number"]), _lower(paragraph), _lower(point)]),
        )
    for match in ANNEX.finditer(query):
        if not (match["section"] or match["point"]):
            continue  # a whole annex: see the module docstring
        letter = match["letter"] or match["buchstabe"]
        sections = [match["section"].upper()] if match["section"] else []
        parts = [match["annex"].upper(), *sections, match["point"], _lower(letter)]
        yield match.start(), _join("annex", parts)
    for match in RECITAL.finditer(query):
        yield match.start(), f"recital:{match['number']}"


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
