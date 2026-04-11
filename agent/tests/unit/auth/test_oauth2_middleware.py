from typing import Any

import pytest
from authlib.jose import JsonWebKey, KeySet, jwt
from authlib.jose.errors import ExpiredTokenError, InvalidClaimError, InvalidTokenError
from pydantic_core import Url
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import src.auth.oauth2 as oauth2_module
from src.auth.constants import EXCLUDED_PATHS
from src.auth.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import OAuthDiscoveredJwksPolicyConfig


ISSUER_URL = "https://issuer.example"
_JWK_DICT = {
    "kty": "oct",
    "k": "c2VjcmV0c2VjcmV0c2VjcmV0c2VjcmV0",
    "kid": "test-key-id",
}


def _build_jwk_set() -> KeySet:
    return JsonWebKey.import_key_set({"keys": [_JWK_DICT]})


def _encode_access_token(*, claims: dict[str, Any]) -> str:
    key = JsonWebKey.import_key(_JWK_DICT)
    token = jwt.encode({"alg": "HS256", "kid": "test-key-id"}, claims, key)
    return token.decode("utf-8")


def _build_request(*, path: str, authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 123),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _build_middleware(*, config: OAuthPoliciesConfig | None = None):
    async def app(scope, receive, send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=config
        or OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
                rfc9068=None,
                claims={},
            )
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("excluded_path", EXCLUDED_PATHS)
async def test_dispatch_bypasses_auth_for_excluded_paths(excluded_path: str) -> None:
    middleware = _build_middleware()
    request = _build_request(
        path=excluded_path,
        authorization=None,
    )
    called = False

    async def call_next(_: Request) -> Response:
        nonlocal called
        called = True
        return JSONResponse({"ok": True}, status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert called
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authorization_header",
    [None, ""],
)
async def test_dispatch_returns_401_when_authorization_header_is_missing(
    authorization_header: str | None,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization=authorization_header)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when auth header is missing")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Bearer realm="test-realm"'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authorization_header",
    ["Basic abc", "Bearer", " "],
)
async def test_dispatch_returns_invalid_request_for_malformed_bearer_header(
    authorization_header: str,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization=authorization_header)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called for malformed bearer auth")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_request", '
        'error_description="Authorization header must use Bearer token"'
    )


@pytest.mark.asyncio
async def test_dispatch_returns_expired_token_error_when_validation_detects_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization="Bearer expired-token")

    async def fetch_jwk_set(*, jwtPolicyConfig, metadata=None):
        return object()

    monkeypatch.setattr(middleware, "_fetch_jwk_set", fetch_jwk_set)

    def _raise_expired(_token: str, _jwk_set: object):
        raise ExpiredTokenError(error="expired_token")

    monkeypatch.setattr(middleware, "_validate_access_token", _raise_expired)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called for expired tokens")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_token", '
        'error_description="The access token expired"'
    )


def test_validate_access_token_accepts_tokens_without_optional_date_claims() -> None:
    middleware = _build_middleware()
    token = _encode_access_token(claims={"iss": ISSUER_URL})

    middleware._validate_access_token(token, _build_jwk_set())


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": ISSUER_URL, "exp": 1},
        {"iss": ISSUER_URL, "iat": 9999999999},
        {"iss": ISSUER_URL, "nbf": 9999999999},
    ],
)
def test_validate_access_token_rejects_invalid_registered_date_claim_values(
    claims: dict[str, Any],
) -> None:
    middleware = _build_middleware()
    token = _encode_access_token(claims=claims)

    with pytest.raises((ExpiredTokenError, InvalidTokenError)):
        middleware._validate_access_token(token, _build_jwk_set())


@pytest.mark.parametrize("claim_name", ["exp", "iat", "nbf"])
def test_validate_access_token_rejects_malformed_registered_date_claims(
    claim_name: str,
) -> None:
    middleware = _build_middleware()
    token = _encode_access_token(claims={"iss": ISSUER_URL, claim_name: "invalid"})

    with pytest.raises(InvalidClaimError, match=f"Invalid claim '{claim_name}'"):
        middleware._validate_access_token(token, _build_jwk_set())


@pytest.mark.asyncio
async def test_dispatch_uses_discovered_jwks_uri_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_jwks_url = "https://issuer.example/.well-known/jwks.json"
    captured_jwks_url: str | None = None
    config = OAuthJwtPolicyConfig(
        jwks=OAuthDiscoveredJwksPolicyConfig(),
        rfc9068=None,
        claims={},
    )

    middleware = _build_middleware(config=OAuthPoliciesConfig(jwt=config))

    async def discover_jwks_uri(_metadata=None) -> str:
        return expected_jwks_url

    monkeypatch.setattr(middleware, "_discover_jwks_uri", discover_jwks_uri)

    async def fetch_json(url: str):
        nonlocal captured_jwks_url
        captured_jwks_url = url
        return {"keys": []}

    monkeypatch.setattr(oauth2_module, "fetch_json", fetch_json)
    await middleware._fetch_jwk_set(jwtPolicyConfig=config)

    assert captured_jwks_url == expected_jwks_url


@pytest.mark.asyncio
async def test_dispatch_returns_503_when_jwks_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization="Bearer valid-token")

    async def raise_fetch_jwk_set(*, jwtPolicyConfig, metadata=None):
        raise ValueError("boom")

    monkeypatch.setattr(middleware, "_fetch_jwk_set", raise_fetch_jwk_set)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when JWKS fetch fails")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 503
    assert response.body == b'{"detail":"Failed to fetch JWKS"}'
