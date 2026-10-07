"""The replays' whole-article check (`whole_articles`, E16) over the corpus built from
`data/parsed/`."""

import pytest

from aiact.schemas import Citation, Language, LawVersion, Status, StepName, StepResult
from tests.engine.built_corpus import built_corpus, whole_articles

AMENDED = "ai-act-consolidated"


def step_citing(*provision_ids: str) -> StepResult:
    citations = tuple(
        Citation(
            provision_id=pid,
            document_id=AMENDED,
            law_version=LawVersion.AMENDED,
            language=Language.EN,
            quote=f"Text of {pid}.",
        )
        for pid in provision_ids
    )
    return StepResult(
        step=StepName.TRANSPARENCY,
        decision="A finding.",
        citations=citations,
        status=Status.DECIDED,
    )


def test_whole_articles_split_into_paragraphs_are_flagged() -> None:
    step = step_citing("art:50", "art:5", "art:2")
    assert whole_articles(step) == [f"{AMENDED}/art:50", f"{AMENDED}/art:5", f"{AMENDED}/art:2"]


@pytest.mark.parametrize(
    "provision_id",
    [
        "art:50:1",  # a paragraph
        "art:3:4",  # a definition, numbered like a paragraph
        "art:113:a",  # a point
        "art:16",  # an article made of points, not paragraphs
        "recital:12",  # a recital, one unit
    ],
)
def test_paragraphs_points_and_undivided_units_are_not_flagged(provision_id: str) -> None:
    assert whole_articles(step_citing(provision_id)) == []


def test_the_paragraphs_of_an_article_are_its_numbered_children_only() -> None:
    corpus = built_corpus()
    assert corpus.paragraphs(AMENDED, "art:50") == {f"art:50:{n}" for n in range(1, 8)}
    assert "art:5:1a" in corpus.paragraphs(AMENDED, "art:5")
    assert not {"art:5:1:ba", "art:5:1a:a"} & corpus.paragraphs(AMENDED, "art:5")
    assert corpus.paragraphs(AMENDED, "art:16") == frozenset()
