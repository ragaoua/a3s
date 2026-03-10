import logging
import os
import sys
import json
from json import JSONDecodeError
from hmac import compare_digest
from typing import Any, final, override
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from authlib.jose import JsonWebKey, KeySet, jwt
from authlib.jose.errors import JoseError
from authlib.oauth2.rfc8414 import AuthorizationServerMetadata, get_well_known_url
from google.adk.agents import LlmAgent
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams
from starlette.types import ASGIApp

logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _load_mcp_servers() -> list[str]:
    raw = os.getenv("MCP_SERVERS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]

    return []


def _check_env():
    requiredVars = {
        "LLM_API_URI",
        "LLM_API_KEY",
        "MODEL",
        "AGENT_NAME",
        "AGENT_DESCRIPTION",
        "AGENT_INSTRUCTIONS",
        "LISTEN_PORT",
    }

    missing = [k for k in requiredVars if not os.getenv(k)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    try:
        _ = int(os.environ["LISTEN_PORT"])
    except ValueError:
        logger.error("LISTEN_PORT must be a valid integer")
        sys.exit(1)

    if not (("AGENT_API_KEY" in os.environ) ^ ("OAUTH2_ISSUER_URL" in os.environ)):
        logger.error(
            "Exactly one auth mode must be configured: set either AGENT_API_KEY or OAUTH2_ISSUER_URL (but not both)"
        )
        sys.exit(1)


_check_env()

mcp_servers = _load_mcp_servers()

model = os.environ["MODEL"]
root_agent = LlmAgent(
    model=LiteLlm(
        model=f"openai/{model}",
        api_base=os.environ["LLM_API_URI"],
        api_key=os.environ["LLM_API_KEY"],
    ),
    name=os.environ["AGENT_NAME"],
    description=os.environ["AGENT_DESCRIPTION"],
    instruction=os.environ["AGENT_INSTRUCTIONS"],
    tools=[
        MCPToolset(connection_params=StreamableHTTPConnectionParams(url=url))
        for url in mcp_servers
    ],
)


@final
class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        received_key = request.headers.get("API-Key", "")
        if not compare_digest(received_key, self.api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"WWW-Authenticate": "API-Key"},
            )

        return await call_next(request)


@final
class OAuth2BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Notes: this is a VERY basic auth middleware that's missing many things
    to be considered prod ready, including (but not limited to):
    - Caching the jwks (When token validation fails, re-fetch the jwks and try once more)
    - Support for OIDC in addition to plain oauth2 for jwks discovery
        (use authlib.oidc.discovery.get_well_known_url)
    - Proper handling of token validation errors
    - Audience validation (maybe other claims too ?)
    """

    def __init__(
        self,
        app: ASGIApp,
        issuer_url: str,
        jwks_url: str | None,
        realm: str,
    ):
        super().__init__(app)
        self.issuer_url = issuer_url.rstrip("/")
        self.jwks_url = jwks_url or self._discover_jwks_uri()
        self.jwk_set = self._fetch_jwk_set(self.jwks_url)
        self.realm = realm

    def _fetch_json(self, url: str) -> dict[str, Any]:
        try:
            with urlopen(url, timeout=5) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, JSONDecodeError) as err:
            raise ValueError(f"Failed to fetch JSON from '{url}'") from err

    def _discover_jwks_uri(self) -> str:
        metadata_url = get_well_known_url(self.issuer_url, external=True)
        metadata_raw = self._fetch_json(metadata_url)
        metadata = AuthorizationServerMetadata(metadata_raw)
        metadata.validate_issuer()
        metadata.validate_jwks_uri()

        metadata_issuer = str(metadata.get("issuer", "")).rstrip("/")
        if metadata_issuer != self.issuer_url:
            raise ValueError("Issuer mismatch in OAuth2 authorization server metadata")

        jwks_uri = metadata.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ValueError(
                "OAuth2 authorization server metadata does not contain a valid jwks_uri"
            )

        return jwks_uri

    def _fetch_jwk_set(self, jwks_url: str) -> KeySet:
        jwks_raw = self._fetch_json(jwks_url)
        return JsonWebKey.import_key_set(jwks_raw)

    def _decode_access_token(self, token: str):
        claims = jwt.decode(
            token,
            self.jwk_set,
            claims_options={"iss": {"essential": True, "value": self.issuer_url}},
        )
        claims.validate()
        return claims

    def _unauthorized_error_response(
        self,
        error: str | None = None,
        error_description: str | None = None,
    ) -> JSONResponse:
        authenticate_header = f'Bearer realm="{self.realm}"'

        if error:
            authenticate_header += f', error="{error}"'

        if error_description:
            authenticate_header += f', error_description="{error_description}"'

        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": authenticate_header},
        )

    @override
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return self._unauthorized_error_response()

        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return self._unauthorized_error_response(
                error="invalid_request",
                error_description="Authorization header must use Bearer token",
            )

        token = token.strip()

        try:
            token_payload = self._decode_access_token(token)
            request.state.token_claims = dict(token_payload)
        except Exception as err:
            logger.error("Token validation failed: %s", err)
            if isinstance(err, JoseError) and err.error == "expired_token":
                return self._unauthorized_error_response(
                    error="invalid_token",
                    error_description="The access token expired",
                )
            return self._unauthorized_error_response(
                error="invalid_token",
                error_description="The access token is invalid",
            )

        return await call_next(request)


# NOTE: LISTEN_PORT is necessary here because that's the value that will be
# used for the url for the agent's card. Since this is intended to be run
# inside a container, and the port will be published, this a2a agent needs
# to know on which port it will be exposed. We should probably do the same
# for the host, but we're only working with localhost for now.
a2a_app = to_a2a(root_agent, port=int(os.environ["LISTEN_PORT"]))
if os.getenv("AGENT_API_KEY"):
    logger.info("Auth mode: API Key")
    a2a_app.add_middleware(ApiKeyAuthMiddleware, api_key=os.environ["AGENT_API_KEY"])
else:
    logger.info("Auth mode: OAuth2")
    a2a_app.add_middleware(
        OAuth2BearerAuthMiddleware,
        issuer_url=os.environ["OAUTH2_ISSUER_URL"],
        jwks_url=os.getenv("OAUTH2_JWKS_URL"),
        realm=root_agent.name,
    )
