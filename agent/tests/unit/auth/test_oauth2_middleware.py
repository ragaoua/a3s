import pytest
from authlib.jose.errors import ExpiredTokenError
from pydantic_core import Url
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import src.auth.oauth2 as oauth2_module
from src.auth.constants import EXCLUDED_PATHS
from src.auth.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthDiscoveredJwksPolicyConfig,
    OAuthJwtPoliciesConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)


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
        issuer_url="https://issuer.example",
        realm="test-realm",
        config=config
        or OAuthPoliciesConfig(
            jwt=OAuthJwtPoliciesConfig(
                jwks=OAuthStaticJwksPolicyConfig(
                    url=Url("https://issuer.example/jwks")
                ),
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

    monkeypatch.setattr(
        middleware,
        "_fetch_jwk_set",
        lambda *, jwtPoliciesConfig, metadata=None: object(),
    )

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


@pytest.mark.asyncio
async def test_dispatch_uses_discovered_jwks_uri_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_jwks_url = "https://issuer.example/.well-known/jwks.json"
    captured_jwks_url: str | None = None
    config = OAuthJwtPoliciesConfig(
        jwks=OAuthDiscoveredJwksPolicyConfig(),
        rfc9068=None,
        claims={},
    )

    middleware = _build_middleware(config=OAuthPoliciesConfig(jwt=config))

    monkeypatch.setattr(
        middleware,
        "_discover_jwks_uri",
        lambda _metadata=None: expected_jwks_url,
    )

    def fetch_json(url: str):
        nonlocal captured_jwks_url
        captured_jwks_url = url
        return {"keys": []}

    monkeypatch.setattr(oauth2_module, "fetch_json", fetch_json)

    middleware._fetch_jwk_set(jwtPoliciesConfig=config)

    assert captured_jwks_url == expected_jwks_url


@pytest.mark.asyncio
async def test_dispatch_returns_503_when_jwks_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization="Bearer valid-token")

    monkeypatch.setattr(
        middleware,
        "_fetch_jwk_set",
        lambda *, jwtPoliciesConfig, metadata=None: (_ for _ in ()).throw(
            ValueError("boom")
        ),
    )

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when JWKS fetch fails")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 503
    assert response.body == b'{"detail":"Failed to fetch JWKS"}'
