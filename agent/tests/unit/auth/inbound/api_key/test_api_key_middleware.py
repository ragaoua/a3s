import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.auth.inbound.api_key import ApiKeyAuthMiddleware
from src.auth.inbound.constants import EXCLUDED_PATHS


API_KEY = "s3cret-key"


def _build_request(*, path: str, api_key_header: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if api_key_header is not None:
        headers.append((b"api-key", api_key_header.encode("utf-8")))

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


def _build_middleware(*, api_key: str = API_KEY) -> ApiKeyAuthMiddleware:
    async def app(scope, receive, send):
        return None

    return ApiKeyAuthMiddleware(app=app, api_key=api_key)


@pytest.mark.asyncio
@pytest.mark.parametrize("excluded_path", EXCLUDED_PATHS)
async def test_dispatch_bypasses_auth_for_excluded_paths(excluded_path: str) -> None:
    middleware = _build_middleware()
    request = _build_request(path=excluded_path, api_key_header=None)
    called = False

    async def call_next(_: Request) -> Response:
        nonlocal called
        called = True
        return JSONResponse({"ok": True}, status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert called
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_returns_401_when_api_key_header_is_missing() -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header=None)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when API key is missing")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "API-Key"


@pytest.mark.asyncio
async def test_dispatch_returns_401_when_api_key_header_is_empty() -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header="")

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when API key is empty")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "API-Key"


@pytest.mark.asyncio
async def test_dispatch_returns_401_when_api_key_does_not_match() -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header="wrong-key")

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when API key is invalid")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "API-Key"


@pytest.mark.asyncio
async def test_dispatch_calls_next_when_api_key_matches() -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header=API_KEY)
    called = False

    async def call_next(_: Request) -> Response:
        nonlocal called
        called = True
        return JSONResponse({"ok": True}, status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert called
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_is_case_sensitive_on_api_key_value() -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header=API_KEY.upper())

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called for case-mismatched API key")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_response_body_for_unauthorized_request() -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header=None)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when API key is missing")

    response = await middleware.dispatch(request, call_next)

    assert response.body == b'{"detail":"Unauthorized"}'
