"""Which citations resolve in the corpus, for the citation-existence score (INIT > Metrics).

A citation names its document by `document_id`, which is the corpus `documents.doc_key` (the
manifest id, for example `ai-act-consolidated`; decision 009, and C1 writes the same id into the
parsed provisions). A citation resolves when a provision with its `provision_id` and `language`
exists in a document with that key and, when the citation sets `law_version`, that law version.
The corpus tables are only read.
"""

import psycopg

from aiact.eval.metrics import CitationExists
from aiact.schemas.evidence import Citation

CitationIndex = frozenset[tuple[str, str, str, str | None]]
"""Every corpus provision as (doc_key, provision_id, language, law_version)."""


def load_citation_index(conn: psycopg.Connection) -> CitationIndex:
    rows = conn.execute(
        "select distinct d.doc_key, p.provision_id, p.language, d.law_version "
        "from provisions p join documents d on d.id = p.document_id"
    ).fetchall()
    return frozenset((doc_key, pid, language, version) for doc_key, pid, language, version in rows)


def citation_checker(index: CitationIndex) -> CitationExists | None:
    """A resolver over the index, or None when the corpus is empty (nothing to check against)."""
    if not index:
        return None
    unversioned = frozenset(key[:3] for key in index)

    def exists(citation: Citation) -> bool:
        place = (citation.document_id, citation.provision_id, citation.language.value)
        if citation.law_version is None:
            return place in unversioned
        return (*place, citation.law_version.value) in index

    return exists
