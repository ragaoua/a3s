import pytest
from authlib.jose.errors import ExpiredTokenError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.auth.constants import EXCLUDED_PATHS
from src.auth.oauth2 import OAuth2BearerAuthMiddleware


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


def _build_middleware(*, jwks_url: str | None = "https://issuer.example/jwks"):
    async def app(scope, receive, send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url="https://issuer.example",
        jwks_url=jwks_url,
        realm="test-realm",
        audience="api://agent",
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
async def test_dispatch_sets_request_state_and_calls_next_on_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization="Bearer valid-token")
    expected_claims = {"sub": "test-user", "aud": ["api://agent"]}

    monkeypatch.setattr(
        middleware,
        "_fetch_jwk_set",
        lambda _: object(),
    )
    monkeypatch.setattr(
        middleware,
        "_get_validated_access_token_claims",
        lambda _token, _jwk_set: expected_claims,
    )

    async def call_next(req: Request) -> Response:
        assert req.state.authorization_header == "Bearer valid-token"
        return JSONResponse({"ok": True}, status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_returns_expired_token_error_when_validation_detects_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", authorization="Bearer expired-token")

    monkeypatch.setattr(middleware, "_fetch_jwk_set", lambda _: object())

    def _raise_expired(_token: str, _jwk_set: object):
        raise ExpiredTokenError(error="expired_token")

    monkeypatch.setattr(
        middleware, "_get_validated_access_token_claims", _raise_expired
    )

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
    middleware = _build_middleware(jwks_url=None)
    request = _build_request(path="/rpc", authorization="Bearer valid-token")
    expected_jwks_url = "https://issuer.example/.well-known/jwks.json"
    captured_jwks_url: str | None = None

    monkeypatch.setattr(middleware, "_discover_jwks_uri", lambda: expected_jwks_url)

    def _fetch_jwk_set(jwks_url: str):
        nonlocal captured_jwks_url
        captured_jwks_url = jwks_url
        return object()

    monkeypatch.setattr(middleware, "_fetch_jwk_set", _fetch_jwk_set)
    monkeypatch.setattr(
        middleware,
        "_get_validated_access_token_claims",
        lambda _token, _jwk_set: {"sub": "test-user"},
    )

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert captured_jwks_url == expected_jwks_url
