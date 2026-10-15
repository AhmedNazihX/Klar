"""`POST /documents/vendor-letter` (P28) on the loaded corpus: the route's own `law_quotes`
reads the Art. 5(1) points through `get_provision` (decision 031), and quotes them exactly as
the corpus built from `data/parsed/` does, which the other tests use. Skipped when the corpus
isn't loaded (failed instead in CI's isolation job), through the `corpus` fixture of
`tests/db/conftest.py`."""

from collections.abc import AsyncIterator
from contextlib import nullcontext
from datetime import date

import httpx
import psycopg
import pytest

from aiact.api import create_app
from aiact.api.dependencies import database
from aiact.api.documents import CorpusQuotes, VendorLetter, corpus_source
from aiact.schemas import Language, LawVersion
from aiact.settings import get_settings
from tests.api.conftest import BASE_URL, api_settings
from tests.drafting.vendor_builders import EMOTIONS, corpus_quotes, prohibited_result
from tests.drafting.vendor_builders import prohibited_step as step_citing

pytestmark = pytest.mark.db

POINTS = ("art:5:1:f", "art:5:1:ba", "art:5:1:bb")
DECEMBER = date(2026, 12, 10)


@pytest.mark.parametrize("language", list(Language))
@pytest.mark.parametrize(
    ("law_version", "as_of", "points"),
    [(LawVersion.AMENDED, DECEMBER, POINTS), (LawVersion.ORIGINAL, None, POINTS[:1])],
    ids=["amended", "original"],
)
def test_the_database_quotes_as_the_built_corpus_does(
    corpus: psycopg.Connection,
    language: Language,
    law_version: LawVersion,
    as_of: date | None,
    points: tuple[str, ...],
) -> None:
    from_database = CorpusQuotes(
        lambda: corpus_source(lambda: nullcontext(corpus)), get_settings().aiact_data_dir
    )
    expected = corpus_quotes()(points, language, law_version, as_of)
    assert from_database(points, language, law_version, as_of) == expected


@pytest.fixture
async def client(corpus: psycopg.Connection) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(api_settings())
    app.dependency_overrides[database] = lambda: lambda: nullcontext(corpus)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as test_client:
        yield test_client


@pytest.mark.anyio
async def test_the_route_quotes_the_database(client: httpx.AsyncClient) -> None:
    result = prohibited_result(step_citing(EMOTIONS))
    body = {"result": result.model_dump(mode="json"), "language": "de"}
    response = await client.post("/documents/vendor-letter", json=body)
    assert response.status_code == 200
    letter = VendorLetter.model_validate(response.json())
    [quote] = next(s.quotes for s in letter.document.sections if s.key == "finding")
    expected = corpus_quotes()(("art:5:1:f",), Language.DE, LawVersion.AMENDED, result.as_of)
    assert (quote,) == expected
    assert all(check.passed for check in letter.checks)


@pytest.mark.anyio
async def test_the_documents_draft_route_quotes_the_database_too(
    client: httpx.AsyncClient,
) -> None:
    """P9's `POST /documents/draft` lists the vendor message and drafts it through the same
    `law_quotes`, with no override: the corpus's text, never the posted result's."""
    result = prohibited_result(step_citing(EMOTIONS))
    body = {
        "result": result.model_dump(mode="json"),
        "language": "en",
        "template": "vendor_message_prohibited",
    }
    response = await client.post("/documents/draft", json=body)
    assert response.status_code == 200
    quotes = [q for s in response.json()["document"]["sections"] for q in s["quotes"]]
    expected = corpus_quotes()(("art:5:1:f",), Language.EN, LawVersion.AMENDED, result.as_of)
    assert quotes == [quote.model_dump(mode="json") for quote in expected]
    assert all(check["passed"] for check in response.json()["checks"])
