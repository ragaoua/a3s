"""Helpers shared by the persistence integration suites (sessions and tasks).

`fetch_rows` reads directly from whichever backend (sqlite or postgres) is
under test; `send_message` and `get_task` drive the agent over A2A.

Note: queries passed to `fetch_rows` use f-string interpolation, because sqlite
and postgres use different placeholders for parameterized queries. For a test
setup, the "SQL injection" risk induced by f-strings isn't a real concern.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
from a2a.client import A2AClient
from a2a.types import (
    GetTaskRequest,
    GetTaskResponse,
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
    TaskQueryParams,
)
from src.config.types.persistence import PostgresUrl, SqliteUrl
from tests.common.a2a import create_send_message_payload, wait_for_agent_card


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


async def send_message(
    base_url: str,
    *,
    text: str,
    context_id: str,
    headers: dict[str, str] | None = None,
) -> Task:
    async with httpx.AsyncClient(
        headers=headers, timeout=httpx.Timeout(30, connect=5)
    ) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                **create_send_message_payload(text=text, context_id=context_id)
            ),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert isinstance(response.root.result, Task)
    return response.root.result


async def get_task(
    base_url: str,
    task_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> GetTaskResponse:
    async with httpx.AsyncClient(
        headers=headers, timeout=httpx.Timeout(30, connect=5)
    ) as httpx_client:
        agent_card = await wait_for_agent_card(base_url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        return await client.get_task(
            GetTaskRequest(id=str(uuid4()), params=TaskQueryParams(id=task_id))
        )
