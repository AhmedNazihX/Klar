"""A direct Postgres connection for server-only tables (corpus, eval records): RLS is on and the
Data API roles have no grants, so the backend writes them over `DATABASE_URL`."""

import psycopg

from aiact.settings import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """DATABASE_URL is not set."""


def connect() -> psycopg.Connection:
    """An autocommit connection to the database in DATABASE_URL."""
    url = get_settings().database_url
    if url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL is not set; see backend/.env.example")
    return psycopg.connect(url.get_secret_value(), autocommit=True)
