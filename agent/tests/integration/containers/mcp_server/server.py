"""MCP server used by the integration suite.

Validates inbound JWTs against a Keycloak (or any OIDC) issuer's JWKS and
exposes a couple of trivial tools. Configuration comes from env vars so the
test suite can point it at the right issuer / audience.
"""

import os
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

ISSUER = os.environ["ISSUER"]
AUDIENCE = os.environ["AUDIENCE"]
RESOURCE_SERVER_URL = os.environ["RESOURCE_SERVER_URL"]
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "3000"))


class KeycloakJwtVerifier(TokenVerifier):
    def __init__(self, *, issuer: str, audience: str) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks_client: PyJWKClient | None = None

    def _get_jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            jwks_uri = self._discover_jwks_uri()
            self._jwks_client = PyJWKClient(jwks_uri, cache_keys=True)
        return self._jwks_client

    def _discover_jwks_uri(self) -> str:
        discovery_url = self._issuer.rstrip("/") + "/.well-known/openid-configuration"
        response = httpx.get(discovery_url, timeout=10.0)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        jwks_uri = payload.get("jwks_uri")
        if not isinstance(jwks_uri, str):
            raise RuntimeError(
                f"OIDC discovery at {discovery_url} did not return a jwks_uri"
            )
        return jwks_uri

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            signing_key = self._get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat"]},
            )
        except (jwt.PyJWTError, httpx.HTTPError, RuntimeError):
            return None

        client_id = payload.get("azp") or payload.get("client_id") or ""
        scope_claim = payload.get("scope", "")
        scopes = scope_claim.split() if isinstance(scope_claim, str) else []
        expires_at = payload.get("exp")

        return AccessToken(
            token=token,
            client_id=str(client_id),
            scopes=scopes,
            expires_at=int(expires_at)
            if isinstance(expires_at, (int, float))
            else None,
        )


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


def build_app() -> FastMCP:
    _wait_for_issuer_ready(ISSUER)

    verifier = KeycloakJwtVerifier(issuer=ISSUER, audience=AUDIENCE)
    auth_settings = AuthSettings(
        issuer_url=AnyHttpUrl(ISSUER),
        resource_server_url=AnyHttpUrl(RESOURCE_SERVER_URL),
    )

    mcp = FastMCP(
        name="a3s-test-mcp",
        host=HOST,
        port=PORT,
        stateless_http=True,
        log_level="INFO",
        token_verifier=verifier,
        auth=auth_settings,
    )

    @mcp.tool(name="add", description="Add two integers")
    def add(a: int, b: int) -> int:
        return a + b

    return mcp


if __name__ == "__main__":
    build_app().run(transport="streamable-http")
