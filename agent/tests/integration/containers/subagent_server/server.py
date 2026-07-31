"""A2A subagent used by the integration suite.

Exposes a minimal A2A-spec server that validates inbound JWTs against a
Keycloak (or any OIDC) issuer's JWKS on the RPC endpoint, and echoes back a
deterministic response so the test suite can assert on round-trip content.
The agent-card endpoint is intentionally left open — that's the convention
the parent agent follows on its own inbound side, and ADK's RemoteA2aAgent
fetches the card during initialisation.
"""

import os
import time
from typing import Any

import httpx
import jwt
import uvicorn
from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import (
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    DEFAULT_RPC_URL,
    PROTOCOL_VERSION_CURRENT,
    TransportProtocol,
)
from jwt import PyJWKClient
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing_extensions import override


ISSUER = os.environ["ISSUER"]
AUDIENCE = os.environ["AUDIENCE"]
JWKS_URI = os.environ["JWKS_URI"]
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3000"))
PUBLIC_URL = os.environ["PUBLIC_URL"]
RESPONSE_TEXT = os.environ.get("RESPONSE_TEXT", "Subagent acknowledged the request.")

# Routes that don't require a Bearer token — the agent card must be reachable
# so RemoteA2aAgent can resolve it during init.
_PUBLIC_PATHS: frozenset[str] = frozenset({AGENT_CARD_WELL_KNOWN_PATH})


class JwtBearerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, issuer: str, audience: str, jwks_uri: str) -> None:
        super().__init__(app)
        self._issuer: str = issuer
        self._audience: str = audience
        self._jwks_client: PyJWKClient = PyJWKClient(jwks_uri, cache_keys=True)

    @override
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat"]},
            )
        except (jwt.PyJWTError, httpx.HTTPError, RuntimeError, KeyError):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        return await call_next(request)


class StaticReplyExecutor(AgentExecutor):
    """Replies with a fixed text message regardless of the request payload."""

    @override
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = new_text_message(RESPONSE_TEXT)
        message.context_id = context.context_id
        message.task_id = context.task_id
        await event_queue.enqueue_event(message)

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # No long-running state to cancel.
        return None


def _wait_for_issuer_ready(issuer: str, *, timeout_seconds: float = 60.0) -> None:
    discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(discovery_url, timeout=5.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1.0)
    raise RuntimeError(
        f"OIDC discovery at {discovery_url} did not become ready in {timeout_seconds}s"
    ) from last_error


def build_app() -> Starlette:
    _wait_for_issuer_ready(ISSUER)

    agent_card = AgentCard(
        name="a3s-test-subagent",
        description="Deterministic echo subagent used by the agent integration suite.",
        supported_interfaces=[
            AgentInterface(
                url=PUBLIC_URL,
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        version="0.0.1",
        capabilities=AgentCapabilities(streaming=True, extended_agent_card=False),
        skills=[
            AgentSkill(
                id="echo",
                name="echo",
                description="Returns a fixed message.",
                tags=["echo"],
            )
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=StaticReplyExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    app = Starlette()
    app.add_middleware(
        JwtBearerMiddleware,
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_uri=JWKS_URI,
    )

    app.routes.extend([
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(request_handler, DEFAULT_RPC_URL),
    ])

    return app


if __name__ == "__main__":
    uvicorn.run(build_app(), host=HOST, port=PORT)
