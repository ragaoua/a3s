import pytest
from a2a.types import Task

from tests.common.a2a import (
    A2aServerFixture,
    get_adk_data_parts,
    get_artifact_text_parts,
    send_message,
)
from tests.common.keycloak import KeycloakFixture
from tests.integration.subagents.conftest import PEER_SUBAGENT_NAME

SUBAGENT_REPLY = "Subagent acknowledged the request."


def _peer_subagent_call_and_response(task: Task) -> tuple[dict, dict]:
    """The peer subagent's call args and reply, as ADK recorded them."""
    call = next(
        c
        for c in get_adk_data_parts(task, "function_call")
        if c["name"] == PEER_SUBAGENT_NAME
    )
    response = next(
        r
        for r in get_adk_data_parts(task, "function_response")
        if r["name"] == PEER_SUBAGENT_NAME
    )["response"]
    return call, response


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

    task = await send_message(
        agent_with_client_credentials_peer_subagent.base_url,
        text="Ask the helper to chime in",
    )

    assert "Subagent answered, summarising now." in get_artifact_text_parts(task)

    helper_call, helper_response = _peer_subagent_call_and_response(task)
    assert helper_call["args"] == {"request": forwarded_request}
    assert helper_response["result"] == SUBAGENT_REPLY


@pytest.mark.asyncio
async def test_agent_forwards_inbound_bearer_to_oauth_protected_peer_subagent(
    agent_with_token_forward_peer_subagent: A2aServerFixture,
    keycloak: KeycloakFixture,
) -> None:
    """`oauth_token_forward`: the parent puts the caller's own inbound bearer on
    the outbound A2A request.

    The subagent container rejects any request whose bearer doesn't validate
    against Keycloak's JWKS, so a subagent reply is proof the header actually
    made it onto the wire — not merely onto the outbound call context.
    """
    forwarded_request = "Please chime in"
    agent_with_token_forward_peer_subagent.mock_llm.stub_tool_call(
        name=PEER_SUBAGENT_NAME,
        arguments={"request": forwarded_request},
        call_id="call_helper",
    )
    agent_with_token_forward_peer_subagent.mock_llm.stub_response(
        "Subagent answered, summarising now."
    )

    task = await send_message(
        agent_with_token_forward_peer_subagent.base_url,
        text="Ask the helper to chime in",
        headers={"Authorization": f"Bearer {keycloak.mint_user_access_token()}"},
    )

    assert "Subagent answered, summarising now." in get_artifact_text_parts(task)

    helper_call, helper_response = _peer_subagent_call_and_response(task)
    assert helper_call["args"] == {"request": forwarded_request}
    assert helper_response["result"] == SUBAGENT_REPLY
