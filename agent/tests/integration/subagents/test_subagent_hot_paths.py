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

from tests.common.a2a import (
    A2aServerFixture,
    create_send_message_payload,
    get_adk_data_parts,
    wait_for_agent_card,
)
from tests.integration.subagents.conftest import PEER_SUBAGENT_NAME


@pytest.mark.asyncio
async def test_agent_delegates_to_oauth_protected_peer_subagent_with_client_credentials_token(
    agent_with_client_credentials_peer_subagent: A2aServerFixture,
) -> None:
    """Happy path: parent agent fetches a token from Keycloak, invokes the
    peer subagent through the AgentTool surface, and the subagent's response
    flows back into the parent's final answer."""
    forwarded_request = "Please chime in"
    agent_with_client_credentials_peer_subagent.mock_llm.stub_tool_call(
        name=PEER_SUBAGENT_NAME,
        arguments={"request": forwarded_request},
        call_id="call_helper",
    )
    agent_with_client_credentials_peer_subagent.mock_llm.stub_response(
        "Subagent answered, summarising now."
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as httpx_client:
        agent_card = await wait_for_agent_card(
            agent_with_client_credentials_peer_subagent.base_url, httpx_client
        )
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(
                **create_send_message_payload(text="Ask the helper to chime in")
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
    assert "Subagent answered, summarising now." in text_parts

    function_calls = get_adk_data_parts(task, "function_call")
    function_responses = get_adk_data_parts(task, "function_response")

    helper_call = next(c for c in function_calls if c["name"] == PEER_SUBAGENT_NAME)
    assert helper_call["args"] == {"request": forwarded_request}

    helper_response = next(
        r for r in function_responses if r["name"] == PEER_SUBAGENT_NAME
    )["response"]
    assert helper_response["result"] == "Subagent acknowledged the request."
