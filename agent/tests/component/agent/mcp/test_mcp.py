import pytest
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool import McpToolset
from mcp.types import TextContent
from pydantic_core import Url

from src.agent.mcp import get_mcp_toolsets
from src.auth.context import bind_current_authorization_header
from src.config.types import (
    McpServerConfig,
    OAuthTokenForwardAuthConfig,
)
from tests.component.agent.mcp.conftest import (
    ADD_TOOL_NAME,
    ECHO_TOOL_NAME,
    McpServerFixture,
)


@pytest.mark.asyncio
async def test_get_mcp_toolsets_lists_tools_from_server(
    mcp_server: McpServerFixture,
) -> None:
    toolsets = get_mcp_toolsets([McpServerConfig(url=Url(mcp_server.url), auth="none")])
    assert len(toolsets) == 1
    toolset = toolsets[0]
    assert isinstance(toolset, McpToolset)

    try:
        tools = await toolset.get_tools()
    finally:
        await toolset.close()

    tool_names = {tool.name for tool in tools}
    assert tool_names == {ECHO_TOOL_NAME, ADD_TOOL_NAME}


@pytest.mark.asyncio
async def test_get_mcp_toolsets_can_call_tools_on_server(
    mcp_server: McpServerFixture,
) -> None:
    toolsets = get_mcp_toolsets([McpServerConfig(url=Url(mcp_server.url), auth="none")])
    toolset = toolsets[0]
    assert isinstance(toolset, McpToolset)

    try:
        # MCPTool.run_async requires a fully built ADK ToolContext
        # (InvocationContext, Session, services...). To keep this test focused
        # on get_mcp_toolsets' wiring rather than the agent runtime, we drive
        # the toolset's own session manager directly — the same object the
        # tool would use to dispatch a call in production.
        session = await toolset._mcp_session_manager.create_session()  # pyright: ignore[reportPrivateUsage]
        echo_result = await session.call_tool(ECHO_TOOL_NAME, {"text": "hello"})
        add_result = await session.call_tool(ADD_TOOL_NAME, {"a": 2, "b": 3})
    finally:
        await toolset.close()

    assert echo_result.isError is False
    assert isinstance(echo_result.content[0], TextContent)
    assert echo_result.content[0].text == "hello"

    assert add_result.isError is False
    assert isinstance(add_result.content[0], TextContent)
    assert add_result.content[0].text == "5"


@pytest.mark.asyncio
async def test_oauth_token_forward_forwards_inbound_authorization_header_to_mcp_server(
    mcp_server: McpServerFixture,
) -> None:
    inbound_header = "Bearer inbound-test-token"

    toolsets = get_mcp_toolsets(
        [
            McpServerConfig(
                url=Url(mcp_server.url),
                auth=OAuthTokenForwardAuthConfig(mode="oauth_token_forward"),
            )
        ]
    )
    toolset = toolsets[0]
    assert isinstance(toolset, McpToolset)

    try:
        # _execute_with_session is the production path that invokes
        # _header_provider. _oauth_token_forward_header_provider ignores the
        # context (it reads from a ContextVar), so an uninitialised
        # ReadonlyContext is enough to satisfy the truthiness guard.
        stub_context = ReadonlyContext.__new__(ReadonlyContext)
        with bind_current_authorization_header(inbound_header):
            _ = await toolset._execute_with_session(  # pyright: ignore[reportPrivateUsage]
                lambda session: session.call_tool(ECHO_TOOL_NAME, {"text": "hi"}),
                "Failed to call echo tool",
                stub_context,
            )
    finally:
        await toolset.close()

    assert mcp_server.received_authorization_headers
    assert all(
        header == inbound_header for header in mcp_server.received_authorization_headers
    )


@pytest.mark.asyncio
async def test_oauth_token_forward_sends_no_authorization_header_when_inbound_header_is_unbound(
    mcp_server: McpServerFixture,
) -> None:
    toolsets = get_mcp_toolsets(
        [
            McpServerConfig(
                url=Url(mcp_server.url),
                auth=OAuthTokenForwardAuthConfig(mode="oauth_token_forward"),
            )
        ]
    )
    toolset = toolsets[0]
    assert isinstance(toolset, McpToolset)

    try:
        stub_context = ReadonlyContext.__new__(ReadonlyContext)
        _ = await toolset._execute_with_session(  # pyright: ignore[reportPrivateUsage]
            lambda session: session.call_tool(ECHO_TOOL_NAME, {"text": "hi"}),
            "Failed to call echo tool",
            stub_context,
        )
    finally:
        await toolset.close()

    assert not mcp_server.received_authorization_headers
