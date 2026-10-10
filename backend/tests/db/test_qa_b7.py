"""P7 on B7's Q&A set over the real corpus (C8's DoD addition): every unanswerable question gets
the outside-the-corpus answer with no citation, and every answerable one still reaches the model.

The search runs on the local corpus with Qwen3 query embeddings replayed from
`tests/recordings/db/test_qa_b7/`; the unanswerable test also replays Luna's answers (the
questions close in topic, such as the DSA's, pass the search's cut-off, and the model must find
the sources don't answer them). Unanswerable items have no reference answer, so the test checks
that the assistant declines, never the text (B7's note).

The recordings are made by the orchestrator once the reviews are done:
`uv run pytest tests/db/test_qa_b7.py --record-mode=once -q`, then drop `PENDING`.
"""

from datetime import date

import psycopg
import pytest
from langchain_core.messages import AIMessage
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.corpus.embed import ARMS
from aiact.eval.cases import load_qa_items
from aiact.llm.embeddings import OpenRouterEmbeddings
from aiact.llm.structured import ChatRoute
from aiact.qa import AnswerKind, Searcher, answer_question
from aiact.qa.clients import qa_chat
from aiact.retrieval.search import SearchResults, search_ai_act
from aiact.schemas import Language, LawVersion
from aiact.settings import Settings
from tests.qa.test_answer import RecordingChat

pytestmark = pytest.mark.db

ON = date(2026, 10, 10)
"""The date searched, fixed so a replay sends the requests recorded."""
QWEN3 = ARMS["qwen3"]
DIMS = 1536
LUNA = "openai/gpt-6-luna-20260922"
LUNA_PROVIDER = "azure/eu"

PENDING = pytest.mark.xfail(
    strict=True,
    raises=CannotOverwriteExistingCassetteException,
    reason="recording pending (P7): uv run pytest tests/db/test_qa_b7.py --record-mode=once -q",
)
"""Until the orchestrator records the embeddings and Luna's answers; drop it after recording."""

ITEMS = load_qa_items()
ANSWERABLE = tuple(item for item in ITEMS if item.answerable)
UNANSWERABLE = tuple(item for item in ITEMS if not item.answerable)


def _require_embedded_corpus(db: psycopg.Connection) -> None:
    row = db.execute(
        "select count(*) from provision_embeddings where model = %s and dims = %s",
        (QWEN3.model, DIMS),
    ).fetchone()
    if row is None or row[0] < 1000:
        pytest.skip("the corpus isn't embedded; run `aiact corpus load` and `aiact corpus embed`")


def _searcher(db: psycopg.Connection, settings: Settings) -> Searcher:
    embedder = OpenRouterEmbeddings(
        model=QWEN3.model, provider=QWEN3.provider, dimensions=DIMS, settings=settings
    )

    def search(
        question: str, language: Language, law_version: LawVersion, as_of: date | None
    ) -> SearchResults:
        return search_ai_act(question, language, law_version, as_of or ON, limit=5,
                             embedder=embedder, connection=db)  # fmt: skip

    return search


def test_the_set_has_both_kinds_in_both_languages() -> None:
    """B7's counts, so neither test below passes on an empty list."""
    assert len(UNANSWERABLE) == 9
    assert len(ANSWERABLE) >= 20
    for items in (ANSWERABLE, UNANSWERABLE):
        assert {item.language for item in items} == {Language.EN, Language.DE}


@PENDING
@pytest.mark.vcr
def test_b7_answerable_questions_reach_the_model(
    db: psycopg.Connection, openrouter_settings: Settings
) -> None:
    """The cut-off never turns an answerable question away: each is searched and found, and the
    model is asked (a scripted one here; the answers' quality is V6's measure)."""
    _require_embedded_corpus(db)
    search = _searcher(db, openrouter_settings)
    declined: list[str] = []
    for item in ANSWERABLE:
        chat = RecordingChat(
            messages=iter([AIMessage(content='{"kind": "answered", "answer": "A.", "cited": [1]}')])
        )
        answer = answer_question(item.question, item.language, search=search, route=ChatRoute(chat))
        if not chat.seen or answer.kind is not AnswerKind.ANSWERED:
            declined.append(item.id)
    assert declined == []


@PENDING
@pytest.mark.vcr
def test_b7_unanswerable_questions_get_the_outside_corpus_answer(
    db: psycopg.Connection, openrouter_settings: Settings
) -> None:
    _require_embedded_corpus(db)
    settings = openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER}
    )
    search = _searcher(db, openrouter_settings)
    route = ChatRoute(qa_chat(settings))
    answered: list[tuple[str, str]] = []
    for item in UNANSWERABLE:
        answer = answer_question(item.question, item.language, search=search, route=route)
        if answer.kind is not AnswerKind.OUTSIDE_CORPUS or answer.citations:
            answered.append((item.id, answer.kind.value))
    assert answered == []
