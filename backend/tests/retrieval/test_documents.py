"""`list_documents` (P1, P32): each row is listed under the title the corpus stores for it (the
German rows' German titles come from the manifest); a text only in English keeps its English
title, marked `english_only`. The query is stubbed: the real table, and the loaded corpus's
German titles, are covered by `tests/db/test_api_lookups.py`."""

from datetime import date
from typing import Any

from aiact.retrieval.documents import list_documents
from aiact.schemas import Language


def row(doc_key: str, language: str, title: str, doc_type: str = "law") -> dict[str, Any]:
    return {
        "doc_key": doc_key,
        "title": title,
        "celex": None,
        "doc_type": doc_type,
        "status": "final",
        "law_version": None,
        "is_amending": False,
        "language": language,
        "published_on": date(2026, 5, 19),
        "in_force_from": None,
    }


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: dict[str, Any]) -> "FakeCursor":
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def cursor(self, **kwargs: object) -> FakeCursor:
        return FakeCursor(self.rows)


STORED_DE = "KI-Verordnung (der gespeicherte Titel)"
"""Not the manifest's title: the list must show what the row stores, never a title from code."""
ROWS_DE = [
    row("ai-act", "de", STORED_DE),
    row(
        "guide-art50",
        "en",
        "Commission Guidelines on the transparency obligations under Article 50",
        "guideline",
    ),
]


def test_each_row_is_listed_under_the_title_it_stores() -> None:
    listed = list_documents(Language.DE, connection=FakeConnection(ROWS_DE))  # pyright: ignore[reportArgumentType]
    titles = {d.doc_key: (d.title, d.language, d.english_only) for d in listed.documents}
    assert titles == {
        "ai-act": (STORED_DE, Language.DE, False),
        # Only in English: its English title, marked.
        "guide-art50": (
            "Commission Guidelines on the transparency obligations under Article 50",
            Language.EN,
            True,
        ),
    }


def test_english_rows_keep_their_titles() -> None:
    rows = [row("ai-act", "en", "Regulation (EU) 2024/1689 (AI Act)")]
    listed = list_documents(Language.EN, connection=FakeConnection(rows))  # pyright: ignore[reportArgumentType]
    (document,) = listed.documents
    assert (document.title, document.english_only) == ("Regulation (EU) 2024/1689 (AI Act)", False)
