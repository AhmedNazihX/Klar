"""The API's OpenAPI schema as `frontend/openapi.json`, which `pnpm gen:api` turns into the
frontend's typed client (P1, P4). `aiact api openapi` writes it; `--check` (and a test) fail
when the committed file no longer matches the app."""

import json
from pathlib import Path

from fastapi import FastAPI

from aiact.api.app import create_app
from aiact.settings import BACKEND_DIR, Settings

OPENAPI_FILE = BACKEND_DIR.parent / "frontend" / "openapi.json"


def openapi_json(app: FastAPI | None = None) -> str:
    """The schema as the committed file holds it. The schema doesn't depend on the settings, so
    the default app is built without reading `.env`."""
    app = app or create_app(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def write_openapi(path: Path = OPENAPI_FILE) -> bool:
    """Write the schema to `path`; True when the file changed."""
    text = openapi_json()
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def is_openapi_current(path: Path = OPENAPI_FILE) -> bool:
    """Whether `path` holds the app's current schema."""
    return path.exists() and path.read_text(encoding="utf-8") == openapi_json()
