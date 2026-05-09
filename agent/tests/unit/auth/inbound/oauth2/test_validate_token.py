import json
import time
from typing import Callable

import httpx
from authlib.jose import JsonWebKey, jwt
from pydantic import JsonValue, SecretStr
import pytest
from pydantic_core import Url
from returns.result import Failure, Success
from starlette.types import Receive, Scope, Send

from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredIntrospectionPolicyConfig,
    OAuthDiscoveredJwksPolicyConfig,
)
from src.utils import FetchJson

ISSUER_URL = "https://issuer.example"
WELL_KNOWN_URL = f"{ISSUER_URL}/.well-known/oauth-authorization-server"
STATIC_JWKS_URL = f"{ISSUER_URL}/static-jwks"
DISCOVERED_JWKS_URL = f"{ISSUER_URL}/discovered-jwks"
STATIC_INTROSPECTION_URL = f"{ISSUER_URL}/static-introspect"
DISCOVERED_INTROSPECTION_URL = f"{ISSUER_URL}/discovered-introspect"

CLIENT_ID = "client"
CLIENT_SECRET = SecretStr("secret")

SIGNING_KEY_DICT: dict[str, str] = {
    "kty": "oct",
    "k": "GawgguFyGrWKav7AX4VKUg",
    "kid": "test",
}
JWKS_PAYLOAD: dict[str, JsonValue] = {"keys": [dict(SIGNING_KEY_DICT)]}
METADATA_PAYLOAD: dict[str, JsonValue] = {
    "issuer": ISSUER_URL,
    "jwks_uri": DISCOVERED_JWKS_URL,
    "introspection_endpoint": DISCOVERED_INTROSPECTION_URL,
}

STATIC_JWKS_CONFIG = OAuthStaticJwksPolicyConfig(url=Url(STATIC_JWKS_URL))
DISCOVERED_JWKS_CONFIG = OAuthDiscoveredJwksPolicyConfig()
STATIC_INTROSPECTION_CONFIG = OAuthStaticIntrospectionPolicyConfig(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    endpoint=Url(STATIC_INTROSPECTION_URL),
)
DISCOVERED_INTROSPECTION_CONFIG = OAuthDiscoveredIntrospectionPolicyConfig(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
)


def _valid_token(*, exp_offset: int = 3600) -> str:
    payload: dict[str, JsonValue] = {
        "iss": ISSUER_URL,
        "exp": int(time.time()) + exp_offset,
    }
    key = JsonWebKey.import_key(SIGNING_KEY_DICT)
    token: bytes = jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        {"alg": "HS256", "kid": "test"}, payload, key
    )
    return token.decode("ascii")


def _build_middleware(
    *, config: OAuthPoliciesConfig, fetch_json: FetchJson
) -> OAuth2BearerAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=config,
        fetch_json=fetch_json,
    )


def _route_fetch_json(
    routes: dict[str, dict[str, JsonValue] | Exception],
    *,
    captured_urls: list[str] | None = None,
) -> FetchJson:
    """Build a FetchJson stub that routes each call by URL.

    Each route value is either a JSON payload to return or an Exception to raise.
    Httpx.Request inputs (used for introspection) are matched on their URL.
    Unmatched URLs raise AssertionError to surface unexpected calls.
    """

    async def _fetch_json(
        url: str | httpx.Request,
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        url_str = str(url.url) if isinstance(url, httpx.Request) else url
        if captured_urls is not None:
            captured_urls.append(url_str)
        if url_str not in routes:
            raise AssertionError(f"Unexpected fetch_json call for url: {url_str}")
        result = routes[url_str]
        if isinstance(result, Exception):
            raise result
        return result

    return _fetch_json


@pytest.mark.asyncio
async def test_returns_success_when_only_jwt_policy_and_validation_succeeds() -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS_CONFIG, rfc9068=None, claims={}),
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json({STATIC_JWKS_URL: JWKS_PAYLOAD}),
    )

    res = await middleware._validate_token(_valid_token())  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)


@pytest.mark.asyncio
async def test_returns_success_when_only_introspection_policy_and_token_is_active() -> (
    None
):
    config = OAuthPoliciesConfig(introspection=STATIC_INTROSPECTION_CONFIG)
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json({STATIC_INTROSPECTION_URL: {"active": True}}),
    )

    res = await middleware._validate_token("opaque-token")  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)


@pytest.mark.asyncio
async def test_returns_success_when_both_jwt_and_introspection_policies_succeed() -> (
    None
):
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS_CONFIG, rfc9068=None, claims={}),
        introspection=STATIC_INTROSPECTION_CONFIG,
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json(
            {
                STATIC_JWKS_URL: JWKS_PAYLOAD,
                STATIC_INTROSPECTION_URL: {"active": True},
            }
        ),
    )

    res = await middleware._validate_token(_valid_token())  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)


@pytest.mark.asyncio
async def test_does_not_fetch_authorization_server_metadata_when_not_required() -> None:
    captured: list[str] = []
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS_CONFIG, rfc9068=None, claims={}),
        introspection=STATIC_INTROSPECTION_CONFIG,
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json(
            {
                STATIC_JWKS_URL: JWKS_PAYLOAD,
                STATIC_INTROSPECTION_URL: {"active": True},
            },
            captured_urls=captured,
        ),
    )

    _ = await middleware._validate_token(_valid_token())  # pyright: ignore[reportPrivateUsage]

    assert WELL_KNOWN_URL not in captured


@pytest.mark.asyncio
async def test_fetches_metadata_only_once_when_jwks_and_introspection_are_discovered() -> (
    None
):
    captured: list[str] = []
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=DISCOVERED_JWKS_CONFIG, rfc9068=None, claims={}),
        introspection=DISCOVERED_INTROSPECTION_CONFIG,
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json(
            {
                WELL_KNOWN_URL: METADATA_PAYLOAD,
                DISCOVERED_JWKS_URL: JWKS_PAYLOAD,
                DISCOVERED_INTROSPECTION_URL: {"active": True},
            },
            captured_urls=captured,
        ),
    )

    res = await middleware._validate_token(_valid_token())  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Success)
    assert captured.count(WELL_KNOWN_URL) == 1


@pytest.mark.asyncio
async def test_returns_503_when_required_metadata_fetch_fails() -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=DISCOVERED_JWKS_CONFIG, rfc9068=None, claims={}),
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json({WELL_KNOWN_URL: ValueError("network down")}),
    )

    res = await middleware._validate_token(_valid_token())  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "detail": "Failed to fetch authorization server metadata: network down"
    }


@pytest.mark.asyncio
async def test_returns_503_when_jwks_fetch_fails() -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS_CONFIG, rfc9068=None, claims={}),
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json({STATIC_JWKS_URL: ValueError("jwks down")}),
    )

    res = await middleware._validate_token(_valid_token())  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "detail": "Failed to fetch JWKS from authorization server: jwks down"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_factory", "expected_description"),
    [
        (lambda: _valid_token(exp_offset=-60), "The access token expired"),
        (lambda: "not.a.jwt", "The access token is invalid"),
    ],
    ids=["expired", "malformed"],
)
async def test_returns_401_with_invalid_token_when_jwt_validation_fails(
    token_factory: Callable[[], str], expected_description: str
) -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS_CONFIG, rfc9068=None, claims={}),
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json({STATIC_JWKS_URL: JWKS_PAYLOAD}),
    )

    res = await middleware._validate_token(token_factory())  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_token", '
        f'error_description="{expected_description}"'
    )


@pytest.mark.asyncio
async def test_does_not_call_introspection_when_jwt_validation_fails() -> None:
    captured: list[str] = []
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS_CONFIG, rfc9068=None, claims={}),
        introspection=STATIC_INTROSPECTION_CONFIG,
    )
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json(
            {
                STATIC_JWKS_URL: JWKS_PAYLOAD,
                STATIC_INTROSPECTION_URL: {"active": True},
            },
            captured_urls=captured,
        ),
    )

    res = await middleware._validate_token(_valid_token(exp_offset=-60))  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    assert STATIC_INTROSPECTION_URL not in captured


@pytest.mark.asyncio
async def test_passes_through_introspection_failure_response_unchanged() -> None:
    config = OAuthPoliciesConfig(introspection=STATIC_INTROSPECTION_CONFIG)
    middleware = _build_middleware(
        config=config,
        fetch_json=_route_fetch_json({STATIC_INTROSPECTION_URL: {"active": False}}),
    )

    res = await middleware._validate_token("opaque-token")  # pyright: ignore[reportPrivateUsage]

    assert isinstance(res, Failure)
    response = res.failure()
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_token", '
        'error_description="The access token provided is expired, revoked, '
        'malformed, or invalid for other reasons."'
    )
