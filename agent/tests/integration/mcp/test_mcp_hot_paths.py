import pytest

from tests.common.a2a import (
    A2aServerFixture,
    get_adk_data_parts,
    get_artifact_text_parts,
    send_message,
)


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

    task = await send_message(
        agent_with_client_credentials_mcp.base_url, text="please add 62 and 54"
    )

    assert "Tool responded as expected." in get_artifact_text_parts(task)

    function_calls = get_adk_data_parts(task, "function_call")
    function_responses = get_adk_data_parts(task, "function_response")

    add_call = next(c for c in function_calls if c["name"] == "add")
    assert add_call["args"] == {"a": 6, "b": 2}

    add_response = next(r for r in function_responses if r["name"] == "add")["response"]
    assert add_response["structuredContent"]["result"] == 8
    assert not add_response["isError"]
