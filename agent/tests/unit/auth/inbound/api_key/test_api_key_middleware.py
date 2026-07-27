import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from src.auth.inbound.api_key import ApiKeyAuthMiddleware
from src.auth.inbound.constants import EXCLUDED_PATHS


API_KEY = "s3cret-key"
API_KEY_SHA256 = "817b823905cc7853f381992575a9041fcdb17fc70e776707abfb4d7c59ecbf3f"


def _build_request(
    *,
    path: str,
    api_key_header: str | None = None,
    header_name: str = ApiKeyAuthMiddleware.DEFAULT_HEADER_NAME,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if api_key_header is not None:
        headers.append(
            (header_name.lower().encode("utf-8"), api_key_header.encode("utf-8"))
        )

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


def _build_middleware(
    *,
    header_name: str = ApiKeyAuthMiddleware.DEFAULT_HEADER_NAME,
) -> ApiKeyAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return ApiKeyAuthMiddleware(
        app=app, api_key=API_KEY_SHA256, header_name=header_name
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXCLUDED_PATHS)
async def test_dispatch_bypasses_auth_for_excluded_paths(path: str) -> None:
    middleware = _build_middleware()
    request = _build_request(path=path, api_key_header=None)
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
    "header",
    [
        None,
        "",
        "wrong-key",
        API_KEY.upper(),  # Tests case sensitivity
    ],
)
async def test_dispatch_returns_401_when_api_key_header_missing_or_empty_or_wrong(
    header: str | None,
) -> None:
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header=header)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when API key is invalid")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.body == b'{"detail":"Unauthorized"}'
    assert response.headers["WWW-Authenticate"] == "API-Key"


@pytest.mark.asyncio
async def test_dispatch_returns_401_when_header_carries_the_hash_instead_of_the_key() -> (
    None
):
    """The header must carry the plaintext key: the middleware hashes it and
    compares digests, so presenting the stored digest itself is unauthorized."""
    middleware = _build_middleware()
    request = _build_request(path="/rpc", api_key_header=API_KEY_SHA256)

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when the digest is presented")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401


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
async def test_dispatch_reads_the_key_from_the_configured_header_name() -> None:
    custom_header = "X-My-Api-Key"
    middleware = _build_middleware(header_name=custom_header)
    request = _build_request(
        path="/rpc", api_key_header=API_KEY, header_name=custom_header
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
async def test_dispatch_ignores_the_default_header_when_a_custom_name_is_configured() -> (
    None
):
    custom_header = "X-My-Api-Key"
    middleware = _build_middleware(header_name=custom_header)
    request = _build_request(
        path="/rpc",
        api_key_header=API_KEY,
        header_name=ApiKeyAuthMiddleware.DEFAULT_HEADER_NAME,
    )

    async def call_next(_: Request) -> Response:
        pytest.fail(
            "call_next should not be called when the key is on the wrong header"
        )

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == custom_header
