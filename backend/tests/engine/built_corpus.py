"""The corpus `aiact corpus load` would write, built in memory from the committed `data/parsed/`
(`build_all`), as a `CitationSource` for the citation validator (E9).

CI's backend job has an empty database, so the replays check their citations against this
instead: it follows `get_provision`'s rules (the document by `document_for`, decision 009's
version filter, the slice covering `as_of`, held-out examples hidden unless `include_held_out`,
the English fallback) and
`get_omnibus_provision`'s for the Omnibus, and builds the result with `get_provision`'s own row
picker. `tests/db/test_citations_corpus.py` checks the two agree on the loaded corpus; CI's
isolation job, which loads the corpus, runs it.

The replays also check that no step cites a whole article its text splits into paragraphs
(`whole_articles`, E16): a step cites the paragraphs its decision rests on.
"""

import re
from collections.abc import Callable, Sequence
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from aiact.corpus.build import OMNIBUS_DOC, DocumentLoad, DocumentRow, ProvisionRow, build_all
from aiact.engine.citations import (
    CitationValidator,
    OmnibusChanges,
    check_citations,
    load_omnibus_changes,
)
from aiact.engine.nodes.common import lookup_for
from aiact.engine.state import EngineState
from aiact.retrieval.provisions import (
    AI_ACT_DOC_KEYS,
    Provision,
    document_for,
)
from aiact.retrieval.provisions import _pick as pick  # pyright: ignore[reportPrivateUsage]
from aiact.schemas import Language, LawVersion, StepResult
from aiact.settings import get_settings

Unit = tuple[DocumentRow, ProvisionRow]
UnitKey = tuple[str, str, str]
"""(doc_key, language, provision_id)."""
ARTICLE_ID = re.compile(r"art:\d+[a-z]*")
PARAGRAPH_ID = re.compile(r":\d+[a-z]*")
"""What follows an article id in one of its paragraphs' ids."""


class BuiltCorpus:
    """A `CitationSource` over `DocumentLoad`s instead of the database."""

    def __init__(self, loads: Sequence[DocumentLoad]) -> None:
        units: dict[UnitKey, list[Unit]] = {}
        parts: dict[tuple[str, str], set[str]] = {}
        for load in loads:
            doc = load.document
            for row in load.provisions:
                units.setdefault((doc.doc_key, doc.language, row.provision_id), []).append(
                    (doc, row)
                )
                if row.parent_id is not None:
                    parts.setdefault((doc.doc_key, row.parent_id), set()).add(row.provision_id)
        self._units = {key: tuple(found) for key, found in units.items()}
        self._parts = {key: frozenset(found) for key, found in parts.items()}

    def paragraphs(self, doc_key: str, article_id: str) -> frozenset[str]:
        """The numbered paragraphs (`art:50:1`, `art:5:1a`) the document splits an article
        into, in any language; none for an article of one paragraph or a list of points."""
        found = self._parts.get((doc_key, article_id), frozenset())
        return frozenset(pid for pid in found if PARAGRAPH_ID.fullmatch(pid, len(article_id)))

    def provision(
        self,
        provision_id: str,
        language: Language,
        law_version: LawVersion | None,
        as_of: date | None,
        *,
        include_held_out: bool = False,
    ) -> Provision:
        version = law_version or LawVersion.AMENDED
        doc_key, version, slice_date = document_for(provision_id, version, as_of, AI_ACT_DOC_KEYS)

        def accepts(doc: DocumentRow, row: ProvisionRow) -> bool:
            is_version = doc.law_version in (version.value, None)
            is_visible = include_held_out or not row.is_held_out
            return is_version and not doc.is_amending and is_visible

        return self._pick(provision_id, doc_key, language, slice_date, accepts)

    def omnibus(self, provision_id: str, language: Language, as_of: date | None) -> Provision:
        def accepts(doc: DocumentRow, row: ProvisionRow) -> bool:
            return doc.is_amending and not row.is_held_out

        return self._pick(provision_id, OMNIBUS_DOC, language, as_of, accepts)

    def _pick(
        self,
        provision_id: str,
        doc_key: str,
        language: Language,
        as_of: date | None,
        accepts: Callable[[DocumentRow, ProvisionRow], bool],
    ) -> Provision:
        """The rows the SQL would return, handed to `get_provision`'s own row picker."""
        rows = [
            _selected(doc, row)
            for found_in in dict.fromkeys((language, Language.EN))
            for doc, row in self._units.get((doc_key, found_in.value, provision_id), ())
            if accepts(doc, row) and _covers(row, as_of)
        ]
        return pick(provision_id, rows, language)


def _covers(row: ProvisionRow, as_of: date | None) -> bool:
    if as_of is None:
        return True
    return row.valid_from <= as_of and (row.valid_to is None or as_of < row.valid_to)


def _selected(doc: DocumentRow, row: ProvisionRow) -> dict[str, Any]:
    """A unit as `SELECT_PROVISION`'s columns."""
    return {
        "doc_key": doc.doc_key,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "law_version": doc.law_version,
        "language": doc.language,
        "heading": row.heading,
        "text": row.text,
        "valid_from": row.valid_from,
        "valid_to": row.valid_to,
    }


@cache
def built_corpus(data_dir: Path | None = None) -> BuiltCorpus:
    """The corpus built from `<data_dir>` (default: the settings'), once per session."""
    root = data_dir or get_settings().aiact_data_dir
    return BuiltCorpus(build_all(root / "manifest.yaml", root / "parsed"))


def omnibus_changes() -> OmnibusChanges:
    return load_omnibus_changes(get_settings().aiact_data_dir)


def built_validator() -> CitationValidator:
    """A `CitationValidator` over the built corpus and the committed amendment records."""
    return CitationValidator(source=built_corpus(), omnibus=omnibus_changes())


def unresolved_citations(step: StepResult, state: EngineState) -> list[str]:
    """`document_id/provision_id` of each citation of `step` that doesn't resolve in the built
    corpus on the run's language, law version and date."""
    checked = check_citations(step.citations, lookup_for(state), built_corpus(), omnibus_changes())
    return [f"{c.document_id}/{c.provision_id}" for c in checked.unresolved]


def whole_articles(step: StepResult) -> list[str]:
    """`document_id/provision_id` of each citation of `step` that quotes a whole article its
    text splits into paragraphs (E16): a step cites the paragraphs its decision rests on."""
    corpus = built_corpus()
    return [
        f"{c.document_id}/{c.provision_id}"
        for c in step.citations
        if ARTICLE_ID.fullmatch(c.provision_id)
        and len(corpus.paragraphs(c.document_id, c.provision_id)) > 1
    ]
