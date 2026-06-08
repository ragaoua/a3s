from typing import Any
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


def _adk_data_parts(task: Task, adk_type: str) -> list[dict[str, Any]]:
    return [
        part.root.data
        for artifact in (task.artifacts or [])
        for part in artifact.parts
        if part.root.kind == "data"
        and part.root.metadata is not None
        and part.root.metadata.get("adk_type") == adk_type
    ]


@pytest.mark.asyncio
async def test_agent_calls_oauth_protected_mcp_tool_with_client_credentials_token(
    agent_with_client_credentials_mcp: A2aServerFixture,
) -> None:
    """Happy path: agent fetches a token from Keycloak, calls the MCP server,
    and the tool response flows back into the assistant's final answer."""
    agent_with_client_credentials_mcp.mock_llm.stub_tool_call(
        name="add",
        arguments={"a": 6, "b": 2},
        call_id="call_add",
    )
    agent_with_client_credentials_mcp.mock_llm.stub_response(
        "Tool responded as expected."
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_client_credentials_mcp.base_url, httpx_client
        )
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                **create_send_message_payload(text="please add 62 and 54")
            ),
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
    assert "Tool responded as expected." in text_parts

    function_calls = _adk_data_parts(task, "function_call")
    function_responses = _adk_data_parts(task, "function_response")

    add_call = next(c for c in function_calls if c["name"] == "add")
    assert add_call["args"] == {"a": 6, "b": 2}

    add_response = next(r for r in function_responses if r["name"] == "add")["response"]
    assert add_response["structuredContent"]["result"] == 8
    assert not add_response["isError"]
