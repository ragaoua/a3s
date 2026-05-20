import asyncio
import httpx
import pytest
from pydantic import SecretStr
from pydantic_core import Url
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.auth.context import get_current_authorization_header
from src.auth.inbound import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredIntrospectionPolicyConfig,
    OAuthDiscoveredJwksPolicyConfig,
)
from tests.integration.auth.conftest import (
    SHORT_LIVED_TOKEN_LIFESPAN_SECONDS,
    KeycloakFixture,
)

PROTECTED_PATH = "/protected"


async def _protected(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "auth_header": get_current_authorization_header(),
        }
    )


def _build_client(
    *,
    issuer_url: str,
    policies: OAuthPoliciesConfig,
) -> httpx.AsyncClient:
    app = Starlette(routes=[Route(PROTECTED_PATH, _protected)])
    app.add_middleware(
        OAuth2BearerAuthMiddleware,
        issuer_url=issuer_url,
        realm="a3s-test-realm",
        config=policies,
    )
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    )


def _jwt_only_policies(jwks_url: str | None = None) -> OAuthPoliciesConfig:
    if jwks_url is None:
        jwks = OAuthDiscoveredJwksPolicyConfig()
    else:
        jwks = OAuthStaticJwksPolicyConfig(url=Url(jwks_url))

    return OAuthPoliciesConfig(jwt=OAuthJwtPolicyConfig(jwks=jwks))


def _introspection_only_policies(
    *,
    keycloak: KeycloakFixture,
) -> OAuthPoliciesConfig:
    return OAuthPoliciesConfig(
        introspection=OAuthDiscoveredIntrospectionPolicyConfig(
            client_id=keycloak.confidential_client_id,
            client_secret=SecretStr(keycloak.confidential_client_secret),
        )
    )


@pytest.mark.asyncio
async def test_oauth2_returns_401_when_authorization_header_is_missing(
    keycloak: KeycloakFixture,
) -> None:
    async with _build_client(
        issuer_url=keycloak.issuer_url,
        policies=_jwt_only_policies(),
    ) as client:
        response = await client.get(PROTECTED_PATH)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Bearer realm="a3s-test-realm"'


@pytest.mark.asyncio
async def test_oauth2_returns_401_when_bearer_token_is_invalid(
    keycloak: KeycloakFixture,
) -> None:
    async with _build_client(
        issuer_url=keycloak.issuer_url,
        policies=_jwt_only_policies(),
    ) as client:
        response = await client.get(
            PROTECTED_PATH,
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert "invalid_token" in response.headers["WWW-Authenticate"]


@pytest.mark.asyncio
async def test_oauth2_accepts_valid_jwt(
    keycloak: KeycloakFixture,
) -> None:
    token = keycloak.mint_access_token()

    async with _build_client(
        issuer_url=keycloak.issuer_url,
        policies=_jwt_only_policies(),
    ) as client:
        response = await client.get(
            PROTECTED_PATH,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["auth_header"] == f"Bearer {token}"


@pytest.mark.asyncio
async def test_oauth2_rejects_expired_jwt(
    keycloak: KeycloakFixture,
) -> None:
    token = keycloak.mint_short_lived_access_token()

    # Wait past the configured lifespan to guarantee expiry.
    await asyncio.sleep(SHORT_LIVED_TOKEN_LIFESPAN_SECONDS + 2)

    async with _build_client(
        issuer_url=keycloak.issuer_url,
        policies=_jwt_only_policies(),
    ) as client:
        response = await client.get(
            PROTECTED_PATH,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert "expired" in response.headers["WWW-Authenticate"].lower()


@pytest.mark.asyncio
async def test_oauth2_rejects_jwt_whose_issuer_does_not_match_configured_issuer(
    keycloak: KeycloakFixture,
) -> None:
    token = keycloak.mint_access_token()
    wrong_issuer = f"{keycloak.base_url}/realms/some-other-realm"

    async with _build_client(
        issuer_url=wrong_issuer,
        policies=_jwt_only_policies(jwks_url=keycloak.jwks_url),
    ) as client:
        response = await client.get(
            PROTECTED_PATH,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert "invalid_token" in response.headers["WWW-Authenticate"]


@pytest.mark.asyncio
async def test_oauth2_accepts_token_via_introspection(
    keycloak: KeycloakFixture,
) -> None:
    token = keycloak.mint_access_token()

    async with _build_client(
        issuer_url=keycloak.issuer_url,
        policies=_introspection_only_policies(keycloak=keycloak),
    ) as client:
        response = await client.get(
            PROTECTED_PATH,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_oauth2_rejects_expired_token_via_introspection(
    keycloak: KeycloakFixture,
) -> None:
    token = keycloak.mint_short_lived_access_token()
    await asyncio.sleep(SHORT_LIVED_TOKEN_LIFESPAN_SECONDS + 2)

    async with _build_client(
        issuer_url=keycloak.issuer_url,
        policies=_introspection_only_policies(keycloak=keycloak),
    ) as client:
        response = await client.get(
            PROTECTED_PATH,
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert "invalid_token" in response.headers["WWW-Authenticate"]
