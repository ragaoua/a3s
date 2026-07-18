from __future__ import annotations

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
from src.config.types import SessionsConfig
from tests.common.a2a import create_send_message_payload, wait_for_agent_card
from tests.common.llm import LlmFixture
from tests.integration.common.agent import start_agent_server
from tests.integration.common.session_service_db import SessionServiceDbFixture


async def _send_message(base_url: str, *, text: str, context_id: str) -> Task:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
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
async def test_conversation_is_stored_in_postgres(
    mock_llm: LlmFixture,
    session_service_db: SessionServiceDbFixture,
) -> None:
    sessions_config = SessionsConfig.model_validate(
        {"connect_string": session_service_db.connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Hello from the mock LLM!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        sessions_config=sessions_config,
    ) as agent_server:
        _ = await _send_message(agent_server.base_url, text="hi", context_id=context_id)

    connection = await asyncpg.connect(session_service_db.connect_string)
    try:
        session_row = await connection.fetchrow(
            "SELECT app_name, user_id FROM sessions WHERE id = $1", context_id
        )
        event_count = await connection.fetchval(
            "SELECT count(*) FROM events WHERE session_id = $1", context_id
        )
    finally:
        await connection.close()

    assert session_row is not None
    assert session_row["app_name"] == "Cody"
    # One event for the user message, one for the agent reply
    assert event_count >= 2


@pytest.mark.asyncio
async def test_conversation_survives_server_restart(
    mock_llm: LlmFixture,
    session_service_db: SessionServiceDbFixture,
) -> None:
    sessions_config = SessionsConfig.model_validate(
        {"connect_string": session_service_db.connect_string}
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
    # been prompted with the conversation history loaded from Postgres.
    messages: dict[str, str] = mock_llm.requests[-1].get_json()["messages"]  # pyright: ignore[reportAny]
    system_prompt, first_message, first_response, second_message = messages  # pyright: ignore[reportUnusedVariable]

    assert first_message == {"role": "user", "content": "My name is Ada."}
    assert first_response == {"role": "assistant", "content": "Nice to meet you, Ada!"}
    assert second_message == {"role": "user", "content": "What is my name?"}
