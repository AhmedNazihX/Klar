"""Record/replay for model calls (pytest-recording over vcrpy).

A test marked `@pytest.mark.vcr` replays the HTTP exchanges saved in
`tests/recordings/<test module>/<test name>.yaml`. The default record mode is `none`, so a
request with no recording fails instead of reaching the network. To record, run the test
once with a real key: `uv run pytest tests/llm/test_chat.py --record-mode=once`.

Recordings keep only the `content-type` header on both sides, so the API key, attribution
headers and provider cookies never land on disk.
"""

from pathlib import Path

import pytest
from pydantic import SecretStr
from vcr.request import Request

from aiact.settings import Settings, get_settings

RECORDINGS_DIR = Path(__file__).parent / "recordings"
KEPT_HEADERS = frozenset({"content-type"})
REPLAY_API_KEY = "replay-without-a-key"
"""Stands in for the key in replay mode; recordings are matched without headers."""


def _scrub_request(request: Request) -> Request:
    request.headers = {k: v for k, v in request.headers.items() if k.lower() in KEPT_HEADERS}
    return request


def _scrub_response(response: dict[str, object]) -> dict[str, object]:
    headers = response.get("headers")
    kept = (
        {k: v for k, v in headers.items() if k.lower() in KEPT_HEADERS}
        if isinstance(headers, dict)
        else {}
    )
    return {**response, "headers": kept}


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    return {
        "before_record_request": _scrub_request,
        "before_record_response": _scrub_response,
        "decode_compressed_response": True,
        "match_on": ["method", "scheme", "host", "path", "query", "body"],
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    return str(RECORDINGS_DIR / request.module.__name__.rsplit(".", 1)[-1])


@pytest.fixture
def openrouter_settings(record_mode: str) -> Settings:
    """Real settings while recording; a placeholder key and no `.env` while replaying."""
    if record_mode != "none":
        return get_settings()
    return Settings(_env_file=None, openrouter_api_key=SecretStr(REPLAY_API_KEY))  # pyright: ignore[reportCallIssue]
