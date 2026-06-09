import socket
import threading
import time
from collections.abc import Iterator

import pytest
from starlette.types import ASGIApp, Receive, Scope, Send
import uvicorn
from mcp.server.fastmcp import FastMCP

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth
from tests.component.agent.mcp.fixture import McpServerFactory, McpServerFixture
from tests.component.conftest import IamFixture, build_iam_introspection_guard_app

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


@pytest.fixture
def mcp_server_factory() -> Iterator[McpServerFactory]:
    started: list[tuple[uvicorn.Server, threading.Thread]] = []

    def _factory(iam: IamFixture | None = None) -> McpServerFixture:
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

        inner_app: ASGIApp = mcp.streamable_http_app()
        if iam is not None:
            inner_app = build_iam_introspection_guard_app(inner_app, iam=iam)

        received_authorization_headers: list[str] = []
        capturing_app = _build_authorization_capturing_app(
            inner_app,
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

        started.append((server, thread))
        return McpServerFixture(
            url=f"http://127.0.0.1:{port}/mcp",
            _received_authorization_headers=received_authorization_headers,
        )

    try:
        yield _factory
    finally:
        for server, _ in started:
            server.should_exit = True
        for _, thread in started:
            thread.join(timeout=5)


@pytest.fixture
def mcp_server(mcp_server_factory: McpServerFactory) -> McpServerFixture:
    return mcp_server_factory()


def _build_authorization_capturing_app(
    inner: ASGIApp,
    received: list[str],
) -> ASGIApp:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for key, value in scope.get("headers", []):
                if key == b"authorization":
                    received.append(value.decode("ascii"))
                    break
        await inner(scope, receive, send)

    return app
