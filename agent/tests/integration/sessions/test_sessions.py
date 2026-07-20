"""Session persistence tests, parametrized over the database backends.

Note: queries run through `_fetch_rows` use f-string interpolation, because
sqlite and postgres use different placeholders for parameterized queries. For
a test setup, the "SQL injection" risk induced by the use of f-strings
isn't a real concern.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest
from a2a.client import A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)
from pydantic_core import Url
from src.config.types import (
    OAuthConfig,
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
    SessionsConfig,
)
from src.config.types.sessions import PostgresUrl, SqliteUrl
from tests.common.a2a import create_send_message_payload, wait_for_agent_card
from tests.common.keycloak import KeycloakFixture
from tests.common.llm import LlmFixture
from tests.integration.common.agent import start_agent_server
from tests.integration.common.session_service_db import SessionServiceDbFixture


@pytest.fixture(params=["postgres", "sqlite"])
def sessions_db_connect_string(request: pytest.FixtureRequest, tmp_path: Path) -> str:
    if request.param == "postgres":
        db: SessionServiceDbFixture = request.getfixturevalue("session_service_db")
        return db.connect_string
    return f"sqlite:///{tmp_path / 'sessions.db'}"


async def _fetch_rows(connect_string: PostgresUrl | SqliteUrl, query: str) -> list[Any]:
    """Run a query against the sessions database, whichever backend it is."""
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


async def _send_message(
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


@pytest.mark.asyncio
async def test_conversation_is_stored_in_database(
    mock_llm: LlmFixture,
    sessions_db_connect_string: str,
) -> None:
    sessions_config = SessionsConfig.model_validate(
        {"connect_string": sessions_db_connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Hello from the mock LLM!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        sessions_config=sessions_config,
    ) as agent_server:
        _ = await _send_message(agent_server.base_url, text="hi", context_id=context_id)

    session_rows = await _fetch_rows(
        sessions_config.connect_string.get_secret_value(),
        f"SELECT app_name, user_id FROM sessions WHERE id = '{context_id}'",
    )
    event_count_rows = await _fetch_rows(
        sessions_config.connect_string.get_secret_value(),
        f"SELECT count(*) AS event_count FROM events WHERE session_id = '{context_id}'",
    )

    assert len(session_rows) == 1
    assert session_rows[0]["app_name"] == "Cody"
    # One event for the user message, one for the agent reply
    assert event_count_rows[0]["event_count"] >= 2


@pytest.mark.asyncio
async def test_conversation_survives_server_restart(
    mock_llm: LlmFixture,
    sessions_db_connect_string: str,
) -> None:
    sessions_config = SessionsConfig.model_validate(
        {"connect_string": sessions_db_connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Nice to meet you, Ada!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        sessions_config=sessions_config,
    ) as agent_server:
        _ = await _send_message(
            agent_server.base_url, text="My name is Ada.", context_id=context_id
        )

    mock_llm.stub_response("Your name is Ada.")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        sessions_config=sessions_config,
    ) as agent_server:
        task = await _send_message(
            agent_server.base_url, text="What is my name?", context_id=context_id
        )

    assert task.artifacts is not None
    assert task.artifacts[0].parts[0].root.kind == "text"
    assert task.artifacts[0].parts[0].root.text == "Your name is Ada."

    # The second LLM call, served by a fresh server process state, must have
    # been prompted with the conversation history loaded from the database.
    messages: dict[str, str] = mock_llm.requests[-1].get_json()["messages"]  # pyright: ignore[reportAny]
    system_prompt, first_message, first_response, second_message = messages  # pyright: ignore[reportUnusedVariable]

    assert first_message == {"role": "user", "content": "My name is Ada."}
    assert first_response == {"role": "assistant", "content": "Nice to meet you, Ada!"}
    assert second_message == {"role": "user", "content": "What is my name?"}


@pytest.mark.asyncio
async def test_sessions_are_scoped_by_token_subject(
    mock_llm: LlmFixture,
    sessions_db_connect_string: str,
    keycloak: KeycloakFixture,
) -> None:
    """With oauth2+jwt inbound auth, sessions are partitioned by the token's
    `sub`: a caller reusing another user's context id gets their own fresh
    session instead of accessing/resuming the other user's conversation."""
    sessions_config = SessionsConfig.model_validate(
        {"connect_string": sessions_db_connect_string}
    )
    auth_config = OAuthConfig(
        mode="oauth2",
        issuer_url=Url(keycloak.internal_issuer_url),
        policies=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(keycloak.external_jwks_url)),
            ),
        ),
    )
    context_id = uuid4().hex

    with start_agent_server(
        mock_llm=mock_llm,
        sessions_config=sessions_config,
        auth_config=auth_config,
    ) as agent_server:
        mock_llm.stub_response("Nice to meet you, Ada!")
        token = keycloak.mint_user_access_token(username="alice")
        _ = await _send_message(
            agent_server.base_url,
            text="My name is Ada.",
            context_id=context_id,
            headers={"Authorization": f"Bearer {token}"},
        )

        mock_llm.stub_response("I don't know your name.")
        _ = await _send_message(
            agent_server.base_url,
            text="What is my name?",
            context_id=context_id,
            headers={
                "Authorization": f"Bearer {keycloak.mint_user_access_token(username='bob')}"
            },
        )

    # The sessions table is keyed by (app_name, user_id, id): the same
    # context id yields one session per authenticated subject.
    rows = await _fetch_rows(
        sessions_config.connect_string.get_secret_value(),
        f"SELECT user_id FROM sessions WHERE id = '{context_id}'",
    )

    assert sorted(row["user_id"] for row in rows) == ["alice", "bob"]

    # Bob's LLM call must not have been prompted with any of Alice's
    # conversation, even though he presented the same context id as her.
    messages: list[dict[str, str]] = mock_llm.requests[-1].get_json()["messages"]  # pyright: ignore[reportAny]
    system_prompt, bob_message = messages  # pyright: ignore[reportUnusedVariable]

    assert bob_message == {"role": "user", "content": "What is my name?"}
