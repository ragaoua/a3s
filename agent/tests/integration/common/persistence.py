"""Helpers shared by the persistence integration suites (sessions and tasks).

`fetch_rows` reads directly from whichever backend (sqlite or postgres) is
under test; the A2A side is driven through `tests.common.a2a`.

Note: queries passed to `fetch_rows` use f-string interpolation, because sqlite
and postgres use different placeholders for parameterized queries. For a test
setup, the "SQL injection" risk induced by f-strings isn't a real concern.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import asyncpg
from src.config.types.persistence import PostgresUrl, SqliteUrl


async def fetch_rows(connect_string: PostgresUrl | SqliteUrl, query: str) -> list[Any]:
    """Run a query against the persistence database, whichever backend it is."""
    if connect_string.scheme == "sqlite":
        connection = sqlite3.connect(
            connect_string.unicode_string().removeprefix("sqlite:///")
        )
        connection.row_factory = sqlite3.Row
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    pg_connection = await asyncpg.connect(connect_string.unicode_string())
    try:
        return await pg_connection.fetch(query)
    finally:
        await pg_connection.close()
