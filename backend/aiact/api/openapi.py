"""The API's OpenAPI schema as `frontend/openapi.json`, which `pnpm gen:api` turns into the
frontend's typed client (P1, P4). `aiact api openapi` writes it; `--check` (and a test) fail
when the committed file no longer matches the app. The export doesn't depend on the settings:
it is built from settings without `.env`, and is the same with the served docs turned off."""

import json

from aiact.api.app import create_app
from aiact.settings import BACKEND_DIR, Settings

OPENAPI_FILE = BACKEND_DIR.parent / "frontend" / "openapi.json"


def openapi_json() -> str:
    """The schema as the committed file holds it."""
    app = create_app(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def write_openapi() -> bool:
    """Write the schema to `OPENAPI_FILE`; True when the file changed."""
    text = openapi_json()
    if OPENAPI_FILE.exists() and OPENAPI_FILE.read_text(encoding="utf-8") == text:
        return False
    OPENAPI_FILE.write_text(text, encoding="utf-8")
    return True


def is_openapi_current() -> bool:
    """Whether `OPENAPI_FILE` holds the app's current schema."""
    return OPENAPI_FILE.exists() and OPENAPI_FILE.read_text(encoding="utf-8") == openapi_json()
