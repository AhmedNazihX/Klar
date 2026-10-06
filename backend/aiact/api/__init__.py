"""FastAPI app with streaming progress (P1): `POST /classify` over server-sent events, and the
provision, obligation and document lookups."""

from aiact.api.app import create_app

__all__ = ["create_app"]
