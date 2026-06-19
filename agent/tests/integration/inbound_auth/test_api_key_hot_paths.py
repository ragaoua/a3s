from uuid import uuid4

import httpx
import pytest
from a2a.client import A2AClient, A2AClientHTTPError
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)

from src.auth.inbound import ApiKeyAuthMiddleware
from tests.common.a2a import (
    A2aServerFixture,
    create_send_message_payload,
    wait_for_agent_card,
)
from tests.integration.inbound_auth.conftest import API_KEY


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_with_valid_api_key(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    """Happy path: a request carrying the configured API key in the
    `API-Key` header passes the middleware and the a2a request flows through
    to the stubbed LLM."""
    agent_with_api_key_inbound_auth.mock_llm.stub_response("Authorized response.")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_api_key_inbound_auth.base_url, httpx_client
        )

    async with httpx.AsyncClient(
        headers={ApiKeyAuthMiddleware.HEADER_NAME: API_KEY},
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        response = await client.send_message(request)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert isinstance(response.root.result, Task)
    task = response.root.result
    assert task.artifacts is not None

    text_parts = [
        part.root.text
        for artifact in task.artifacts
        for part in artifact.parts
        if part.root.kind == "text"
    ]
    assert "Authorized response." in text_parts


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_with_invalid_api_key(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_api_key_inbound_auth.base_url, httpx_client
        )

    async with httpx.AsyncClient(
        headers={ApiKeyAuthMiddleware.HEADER_NAME: "wrong-key"},
        timeout=httpx.Timeout(30, connect=5),
    ) as httpx_client:
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        with pytest.raises(A2AClientHTTPError) as exc:
            _ = await client.send_message(request)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_agent_rejects_a2a_request_without_api_key_header(
    agent_with_api_key_inbound_auth: A2aServerFixture,
) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_api_key_inbound_auth.base_url, httpx_client
        )
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(**create_send_message_payload(text="ping")),
        )
        with pytest.raises(A2AClientHTTPError) as exc:
            _ = await client.send_message(request)

    assert exc.value.status_code == 401
