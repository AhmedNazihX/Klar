"""The prompt helpers the checks share (`engine/nodes/common.py`): the passage cut and the
passages a model answer names by number."""

from datetime import date

from aiact.engine.nodes.common import MAX_PASSAGE_CHARS, clipped, named_passages
from aiact.retrieval.search import SearchHit
from aiact.schemas import DocumentStatus, Language


def hit(pid: str) -> SearchHit:
    return SearchHit(
        provision_id=pid,
        doc_key="guide-prohibited",
        document_title="Guidelines",
        doc_type="guideline",
        law_version=None,
        status=DocumentStatus.FINAL,
        language=Language.EN,
        heading=None,
        text=f"Text of {pid}.",
        valid_from=date(2025, 2, 4),
        valid_to=None,
        score=0.03,
        vector_rank=1,
        keyword_rank=None,
        similarity=0.6,
        keyword_idf=None,
    )


def test_a_long_text_is_cut_to_the_limit_and_marked() -> None:
    text = "x" * 5000
    assert clipped(text) == "x" * MAX_PASSAGE_CHARS + " […]"


def test_a_text_at_the_limit_is_left_alone() -> None:
    text = "y" * MAX_PASSAGE_CHARS
    assert clipped(text) == text


def test_only_named_passages_in_range_are_returned_each_once() -> None:
    hits = (hit("guide:a"), hit("guide:b"), hit("guide:c"))
    assert named_passages([0, -1, 2, 2, 9], hits) == (hits[1],)
