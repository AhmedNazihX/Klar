"""`list_documents`: the texts in the corpus, with their title, status and dates (story P1), for
the interface's "Texts used" and "Answers draw on" lists (decision 026).

No model is involved: one read of the `documents` table, one row per text and law version. The
German row is returned when it exists; otherwise the English one, with `english_only` set (most
guidance exists only in English), as `get_provision` does for a provision's text. The Digital
Omnibus is listed too, marked `is_amending`: results cite it for the changes it made. Each row
keeps the title the corpus stores for its language: the German rows carry their German titles
from `data/manifest.yaml` (P32).
"""

from datetime import date
from typing import Any, Literal, LiteralString

import psycopg
from psycopg.rows import dict_row

from aiact.db import connect
from aiact.schemas import DISCLAIMER, DocumentStatus, Language, LawVersion
from aiact.schemas.base import ContractModel

SELECT_DOCUMENTS: LiteralString = """
    select distinct on (d.doc_key, d.law_version)
           d.doc_key, d.title, d.celex, d.doc_type, d.status, d.law_version, d.is_amending,
           d.language, d.published_on, d.in_force_from
    from documents d
    where d.language = any(%(languages)s)
    order by d.doc_key, d.law_version, d.language = %(language)s desc
"""
"""One row per (doc_key, law_version): the wanted language first, else English."""


class DocumentInfo(ContractModel):
    """One text of the corpus, as the interface lists it."""

    doc_key: str
    title: str
    celex: str | None
    doc_type: Literal["law", "guideline", "code"]
    status: DocumentStatus
    law_version: LawVersion | None
    """The AI Act text (original or amended); None for guidance and the amending act."""
    is_amending: bool
    """The Digital Omnibus: cited for its changes, never read as the law itself."""
    language: Language
    """The language of `title`; English when `english_only` is set."""
    english_only: bool
    published_on: date | None
    in_force_from: date | None


class DocumentList(ContractModel):
    """Every text the answers can draw on, in `doc_key` order, with the notice."""

    documents: tuple[DocumentInfo, ...]
    disclaimer: str


def list_documents(
    language: Language | str = Language.EN, *, connection: psycopg.Connection | None = None
) -> DocumentList:
    """The corpus's texts in `language` (falling back to English per text). Without a
    `connection`, one is opened from DATABASE_URL."""
    wanted = Language(language)
    params = {"languages": sorted({wanted.value, Language.EN.value}), "language": wanted.value}
    if connection is None:
        with connect() as own_connection:
            rows = _select(own_connection, params)
    else:
        rows = _select(connection, params)
    return DocumentList(
        documents=tuple(_document(row, wanted) for row in rows), disclaimer=DISCLAIMER[wanted]
    )


def _select(connection: psycopg.Connection, params: dict[str, Any]) -> list[dict[str, Any]]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(SELECT_DOCUMENTS, params).fetchall()


def _document(row: dict[str, Any], wanted: Language) -> DocumentInfo:
    return DocumentInfo.model_validate(
        {**row, "english_only": Language(row["language"]) is not wanted}
    )
