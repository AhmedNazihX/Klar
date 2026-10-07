"""`get_provision`: the exact text of one article, annex point, recital or guideline unit (story C5;
INIT > MCP tools).

No model is involved: this is a plain lookup over the corpus tables (decisions 009 and 014).
- **Which document.** An `art:` or `annex:` id is read from the AI Act text of the chosen law
  version: `ai-act` for `original`, `ai-act-consolidated` for `amended` (the default). A
  `recital:` id is always read from the original text, the only one that has recitals. A
  `guide:<doc_key>:…` id names its guideline or code. The decision-009 rule is applied on top:
  `(d.law_version = $v or d.law_version is null) and not d.is_amending`, so the Omnibus itself is
  never returned; a citation of the Omnibus reads it through `get_omnibus_provision` (E9).
- **Which date.** `as_of` resolves only against the amended text and defaults to today; the
  original text is an explicit view (one open slice per unit), never a fallback, so asking for an
  article or annex point in `original` together with `as_of` is an error. A recital ignores
  `as_of` (the Omnibus doesn't amend recitals, decision 014). Guidance always honours `as_of`
  against its own slices, which start at its publication date, whatever the law version.
- **Which language.** When the German text is missing (most guidance exists only in English), the
  English text is returned with `english_only` set. The notice is in the language asked for.
- **Held-out examples.** A Pile B worked example is stored but not retrievable by default
  (decision 012), so it is reported as not found unless `include_held_out` is set.
- **Tracing (V7).** Inside a traced engine run, a lookup is a LangSmith run of its own, with the
  provision id as metadata (`aiact.retrieval.tracing`).
"""

import re
from collections.abc import Mapping
from datetime import date
from functools import partial
from types import MappingProxyType
from typing import Any, LiteralString

import psycopg
from psycopg.rows import dict_row

from aiact.corpus.build import OMNIBUS_DOC
from aiact.db import connect
from aiact.retrieval.tracing import provision_metadata, traced_lookup
from aiact.schemas import DISCLAIMER, DocumentStatus, Language, LawVersion
from aiact.schemas.base import ContractModel

PROVISION_ID_RE = re.compile(r"^[a-z]+(:[A-Za-z0-9_.-]+)+$")
"""The same pattern as the `provisions.provision_id` check (F4)."""
MAX_PROVISION_ID_CHARS = 200
"""The longest provision id the API and the MCP tools accept; real ids are well under 100
characters."""

LAW_PREFIXES = frozenset({"art", "annex"})
RECITAL_PREFIX = "recital"
GUIDANCE_PREFIX = "guide"

AI_ACT_DOC_KEYS: Mapping[LawVersion, str] = MappingProxyType(
    {LawVersion.ORIGINAL: "ai-act", LawVersion.AMENDED: "ai-act-consolidated"}
)
"""The manifest `doc_key` of each AI Act text (decision 009)."""

_SELECT_UNIT: LiteralString = """
    select d.doc_key, d.title, d.doc_type, d.status, d.law_version, p.language,
           p.heading, p.text, p.valid_from, p.valid_to
    from provisions p
    join documents d on d.id = p.document_id and d.language = p.language
    where p.provision_id = %(provision_id)s
      and p.language = any(%(languages)s)
      and d.doc_key = %(doc_key)s
      and (%(as_of)s::date is null or daterange(p.valid_from, p.valid_to) @> %(as_of)s::date)
"""
SELECT_PROVISION: LiteralString = (
    _SELECT_UNIT
    + """
      and (d.law_version = %(law_version)s or d.law_version is null)
      and not d.is_amending
      and (%(include_held_out)s or not p.is_held_out)
"""
)
SELECT_AMENDING_PROVISION: LiteralString = (
    _SELECT_UNIT
    + """
      and d.is_amending
      and not p.is_held_out
"""
)
"""One unit of an amending act: only an explicit Omnibus lookup reads it (decision 009). An
amending act holds no worked example; the held-out filter keeps it that way (decision 012)."""


class ProvisionNotFoundError(LookupError):
    """No text of the provision exists for that document, date and language."""


class Provision(ContractModel):
    """One provision's text, with the version, language and status it comes from and the notice."""

    provision_id: str
    doc_key: str
    document_title: str
    doc_type: str
    law_version: LawVersion | None
    """The AI Act text quoted; None for guidance, which belongs to neither text."""
    status: DocumentStatus
    language: Language
    """The language of `text`; English when `english_only` is set."""
    english_only: bool
    """German was asked for but only the English text exists."""
    heading: str | None
    text: str
    valid_from: date
    valid_to: date | None
    disclaimer: str


@traced_lookup(partial(provision_metadata, max_chars=MAX_PROVISION_ID_CHARS))
def get_provision(
    provision_id: str,
    language: Language | str = Language.EN,
    law_version: LawVersion | str | None = None,
    as_of: date | None = None,
    *,
    include_held_out: bool = False,
    connection: psycopg.Connection | None = None,
    ai_act_doc_keys: Mapping[LawVersion, str] = AI_ACT_DOC_KEYS,
) -> Provision:
    """The text of `provision_id` in `language`, from the law version or the date asked for.

    `law_version` defaults to `amended`; `as_of` (the amended text on that date) defaults to
    today. Plain strings are accepted for the enums. Raises ValueError for a malformed id or an
    `original` + `as_of` request for an article or annex point, and ProvisionNotFoundError when
    no row matches. Without a `connection`, one is opened from DATABASE_URL.
    """
    wanted_language = Language(language)
    version = LawVersion(law_version) if law_version is not None else LawVersion.AMENDED
    doc_key, version, slice_date = document_for(provision_id, version, as_of, ai_act_doc_keys)
    params = {
        "provision_id": provision_id,
        "languages": sorted({wanted_language.value, Language.EN.value}),
        "doc_key": doc_key,
        "law_version": version.value,
        "as_of": slice_date,
        "include_held_out": include_held_out,
    }
    rows = _rows(SELECT_PROVISION, params, connection)
    return _pick(provision_id, rows, wanted_language)


# Traced although no tool-call expectation uses it: every lookup is a run of its own.
@traced_lookup(partial(provision_metadata, max_chars=MAX_PROVISION_ID_CHARS))
def get_omnibus_provision(
    provision_id: str,
    language: Language | str = Language.EN,
    as_of: date | None = None,
    *,
    connection: psycopg.Connection | None = None,
    doc_key: str = OMNIBUS_DOC,
) -> Provision:
    """The text of one unit of the Digital Omnibus itself (an amending instruction or a recital),
    for a citation of the Omnibus (E9): `get_provision` never returns an amending act.

    The Omnibus has one slice per unit from its entry into force; with `as_of`, the slice must
    cover it. The language falls back to English as in `get_provision`. Raises ValueError for a
    malformed id and ProvisionNotFoundError when no row matches.
    """
    if not PROVISION_ID_RE.fullmatch(provision_id):
        raise ValueError(f"malformed provision id {provision_id!r}")
    wanted_language = Language(language)
    params = {
        "provision_id": provision_id,
        "languages": sorted({wanted_language.value, Language.EN.value}),
        "doc_key": doc_key,
        "as_of": as_of,
    }
    rows = _rows(SELECT_AMENDING_PROVISION, params, connection)
    return _pick(provision_id, rows, wanted_language)


def document_for(
    provision_id: str,
    version: LawVersion,
    as_of: date | None,
    ai_act_doc_keys: Mapping[LawVersion, str],
) -> tuple[str, LawVersion, date | None]:
    """The `doc_key` that holds the id, the law version it is read under, and the date its slice
    must cover (None for the original text's single open slice)."""
    if not PROVISION_ID_RE.fullmatch(provision_id):
        raise ValueError(f"malformed provision id {provision_id!r}")
    prefix, first, *_ = provision_id.split(":")
    if prefix in LAW_PREFIXES:
        if version is LawVersion.ORIGINAL:
            if as_of is not None:
                raise ValueError(
                    "as_of resolves only against the amended text; drop it for 'original'"
                )
            return ai_act_doc_keys[version], version, None
        return ai_act_doc_keys[version], version, as_of or date.today()
    if prefix == RECITAL_PREFIX:
        return ai_act_doc_keys[LawVersion.ORIGINAL], LawVersion.ORIGINAL, None
    if prefix == GUIDANCE_PREFIX:
        return first, version, as_of or date.today()
    raise ValueError(f"unknown provision id prefix {prefix!r} in {provision_id!r}")


def _rows(
    query: LiteralString, params: dict[str, Any], connection: psycopg.Connection | None
) -> list[dict[str, Any]]:
    """`query`'s rows over `connection`, or over a short one opened from DATABASE_URL."""
    if connection is None:
        with connect() as own_connection:
            return _select(own_connection, query, params)
    return _select(connection, query, params)


def _select(
    connection: psycopg.Connection, query: LiteralString, params: dict[str, Any]
) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, params).fetchall()


def _pick(provision_id: str, rows: list[dict[str, Any]], wanted: Language) -> Provision:
    """The row in the wanted language, else the English one with `english_only` set."""
    by_language = {Language(row["language"]): row for row in rows}
    row = by_language.get(wanted) or by_language.get(Language.EN)
    if row is None:
        raise ProvisionNotFoundError(f"no text of {provision_id!r} for that version and date")
    return Provision(
        provision_id=provision_id,
        doc_key=row["doc_key"],
        document_title=row["title"],
        doc_type=row["doc_type"],
        law_version=row["law_version"],
        status=row["status"],
        language=row["language"],
        english_only=Language(row["language"]) is not wanted,
        heading=row["heading"],
        text=row["text"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        disclaimer=DISCLAIMER[wanted],
    )
