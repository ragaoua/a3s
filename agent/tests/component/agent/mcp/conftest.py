import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from starlette.applications import Starlette
from starlette.types import Receive, Scope, Send
import uvicorn
from mcp.server.fastmcp import FastMCP

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth

ECHO_TOOL_NAME = "echo"
ADD_TOOL_NAME = "add"

_SERVER_STARTUP_TIMEOUT_SECONDS = 5


@pytest.fixture(autouse=True)
def _clear_outbound_client_credentials_cache() -> Iterator[None]:
    # OAuthClientCredentialsAuth keeps a class-level token cache keyed by
    # (token_endpoint, client_id). The iam fixture is session-scoped, so
    # consecutive tests would otherwise hit the cache and skip the
    # token-endpoint round trip we're trying to exercise.
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE.clear()  # pyright: ignore[reportPrivateUsage]
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE_LOCKS.clear()  # pyright: ignore[reportPrivateUsage]
    yield


@dataclass(frozen=True)
class McpServerFixture:
    url: str
    received_authorization_headers: list[str] = field(default_factory=list)


@pytest.fixture
def mcp_server() -> Iterator[McpServerFixture]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]

    mcp = FastMCP(name="a3s-test-mcp", log_level="WARNING")

    @mcp.tool(name=ECHO_TOOL_NAME, description="Echo the input text back")
    def echo(text: str) -> str:
        return text

    @mcp.tool(name=ADD_TOOL_NAME, description="Add two integers")
    def add(a: int, b: int) -> int:
        return a + b

    received_authorization_headers: list[str] = []
    capturing_app = _build_authorization_capturing_app(
        mcp.streamable_http_app(),
        received_authorization_headers,
    )

    server = uvicorn.Server(
        uvicorn.Config(
            capturing_app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + _SERVER_STARTUP_TIMEOUT_SECONDS
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError(
            f"MCP server did not start within {_SERVER_STARTUP_TIMEOUT_SECONDS}s"
        )

    try:
        yield McpServerFixture(
            url=f"http://127.0.0.1:{port}/mcp",
            received_authorization_headers=received_authorization_headers,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _build_authorization_capturing_app(
    inner: Starlette,
    received: list[str],
):
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for key, value in scope.get("headers", []):
                if key == b"authorization":
                    received.append(value.decode("ascii"))
                    break
        await inner(scope, receive, send)

    return app
