from uuid import uuid4

import httpx
import pytest
from a2a.client import A2AClient
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageSuccessResponse,
    Task,
)

from tests.common.a2a import A2aServerFixture
from tests.integration.utils import create_send_message_payload, wait_for_agent_card


@pytest.mark.asyncio
async def test_agent_accepts_a2a_request_in_no_auth_mode(
    agent_with_no_inbound_auth: A2aServerFixture,
) -> None:
    """No-auth mode: no inbound-auth middleware is wired in, so an a2a
    request without any Authorization header flows straight through to the
    stubbed LLM."""
    agent_with_no_inbound_auth.mock_llm.stub_response("Authorized response.")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_no_inbound_auth.base_url, httpx_client
        )
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
