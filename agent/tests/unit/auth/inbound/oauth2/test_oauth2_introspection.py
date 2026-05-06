import base64
from urllib.parse import parse_qs

import httpx
import pytest
from authlib.oauth2.rfc6750 import InvalidTokenError
from pydantic import SecretStr
from pydantic_core import Url

from src.auth.inbound.oauth2 import (
    OAuth2BearerAuthMiddleware,
    TokenIntrospectionServiceError,
)
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredIntrospectionPolicyConfig,
    OAuthStaticIntrospectionPolicyConfig,
)

ISSUER_URL = "https://issuer.example"
INTROSPECT_URL = f"{ISSUER_URL}/introspect"


def _build_middleware(
    *,
    config: OAuthPoliciesConfig,
    fetch_json=None,
) -> OAuth2BearerAuthMiddleware:
    async def app(scope, receive, send):
        return None

    kwargs = {}
    if fetch_json is not None:
        kwargs["fetch_json"] = fetch_json

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=config,
        **kwargs,
    )


def _static_introspection(
    auth_method: str = "client_secret_basic",
) -> OAuthPoliciesConfig:
    return OAuthPoliciesConfig(
        introspection=OAuthStaticIntrospectionPolicyConfig(
            endpoint=Url(INTROSPECT_URL),
            client_id="my-client",
            client_secret=SecretStr("my-secret"),
            auth_method=auth_method,  # pyright: ignore[reportArgumentType]
        )
    )


def test_get_introspection_request_uses_basic_auth_header() -> None:
    middleware = _build_middleware(config=_static_introspection("client_secret_basic"))

    request = middleware._get_introspection_request(
        token="t",
        endpoint=INTROSPECT_URL,
        auth_method="client_secret_basic",
        client_id="my-client",
        client_secret=SecretStr("my-secret"),
    )

    expected = base64.b64encode(b"my-client:my-secret").decode("ascii")
    assert request.headers["Authorization"] == f"Basic {expected}"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    body = parse_qs(request.content.decode("utf-8"))
    assert body == {"token": ["t"], "token_type_hint": ["access_token"]}


def test_get_introspection_request_uses_post_body_for_client_secret_post() -> None:
    middleware = _build_middleware(config=_static_introspection("client_secret_post"))

    request = middleware._get_introspection_request(
        token="t",
        endpoint=INTROSPECT_URL,
        auth_method="client_secret_post",
        client_id="my-client",
        client_secret=SecretStr("my-secret"),
    )

    assert "Authorization" not in request.headers
    body = parse_qs(request.content.decode("utf-8"))
    assert body == {
        "token": ["t"],
        "token_type_hint": ["access_token"],
        "client_id": ["my-client"],
        "client_secret": ["my-secret"],
    }


def test_get_introspection_request_targets_configured_endpoint() -> None:
    middleware = _build_middleware(config=_static_introspection())

    request = middleware._get_introspection_request(
        token="t",
        endpoint=INTROSPECT_URL,
        auth_method="client_secret_basic",
        client_id="my-client",
        client_secret=SecretStr("my-secret"),
    )

    assert request.method == "POST"
    assert str(request.url) == INTROSPECT_URL


@pytest.mark.asyncio
async def test_introspect_access_token_no_op_when_not_configured() -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(
            jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
            rfc9068=None,
            claims={},
        ),
    )

    async def fetch_json(*args, **kwargs):
        pytest.fail("fetch_json should not be called when introspection is unset")

    middleware = _build_middleware(config=config, fetch_json=fetch_json)

    await middleware._introspect_access_token("any-token")


@pytest.mark.asyncio
async def test_introspect_access_token_active_true_passes() -> None:
    async def fetch_json(url, *, error_cls=ValueError, error_message=None):
        return {"active": True}

    middleware = _build_middleware(
        config=_static_introspection(), fetch_json=fetch_json
    )

    await middleware._introspect_access_token("t")


@pytest.mark.asyncio
async def test_introspect_access_token_active_false_raises_invalid_token() -> None:
    async def fetch_json(url, *, error_cls=ValueError, error_message=None):
        return {"active": False}

    middleware = _build_middleware(
        config=_static_introspection(), fetch_json=fetch_json
    )

    with pytest.raises(InvalidTokenError):
        await middleware._introspect_access_token("t")


@pytest.mark.asyncio
async def test_introspect_access_token_missing_active_raises_service_error() -> None:
    async def fetch_json(url, *, error_cls=ValueError, error_message=None):
        return {}

    middleware = _build_middleware(
        config=_static_introspection(), fetch_json=fetch_json
    )

    with pytest.raises(
        TokenIntrospectionServiceError, match="missing a valid 'active'"
    ):
        await middleware._introspect_access_token("t")


@pytest.mark.asyncio
async def test_introspect_access_token_wraps_discovery_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = OAuthPoliciesConfig(
        introspection=OAuthDiscoveredIntrospectionPolicyConfig(
            client_id="my-client",
            client_secret=SecretStr("my-secret"),
        )
    )
    middleware = _build_middleware(config=config)

    async def boom(_metadata=None) -> str:
        raise ValueError("metadata down")

    monkeypatch.setattr(middleware, "_discover_introspection_endpoint", boom)

    with pytest.raises(
        TokenIntrospectionServiceError,
        match="Failed to discover token introspection endpoint",
    ):
        await middleware._introspect_access_token("t")


@pytest.mark.asyncio
async def test_introspect_access_token_sends_request_to_static_endpoint() -> None:
    captured: dict[str, str] = {}

    async def fetch_json(request, *, error_cls=ValueError, error_message=None):
        assert isinstance(request, httpx.Request)
        captured["url"] = str(request.url)
        return {"active": True}

    middleware = _build_middleware(
        config=_static_introspection(), fetch_json=fetch_json
    )

    await middleware._introspect_access_token("t")

    assert captured["url"] == INTROSPECT_URL
