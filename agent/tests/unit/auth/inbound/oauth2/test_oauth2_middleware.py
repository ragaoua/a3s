from pydantic_core import Url
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from src.auth.inbound.constants import EXCLUDED_PATHS
from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.utils import FetchJson

ISSUER_URL = "https://issuer.example"


def _build_middleware(
    *,
    config: OAuthPoliciesConfig | None = None,
    issuer_url: str,
    fetch_json: FetchJson | None = None,
):
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=issuer_url,
        realm="test-realm",
        config=config
        or OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
                rfc9068=None,
                claims={},
            )
        ),
        **({"fetch_json": fetch_json} if fetch_json is not None else {}),
    )


def _build_request(*, path: str, authorization_header: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization_header is not None:
        headers.append((b"authorization", authorization_header.encode("utf-8")))

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


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXCLUDED_PATHS)
async def test_dispatch_bypasses_auth_for_excluded_paths(path: str) -> None:
    middleware = _build_middleware(issuer_url=ISSUER_URL)
    request = _build_request(path=path, authorization_header=None)
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
    [None, ""],
)
async def test_dispatch_returns_401_when_authorization_header_missing_or_empty(
    header: str | None,
) -> None:
    middleware = _build_middleware(issuer_url=ISSUER_URL)
    request = _build_request(path="/rpc", authorization_header=header)

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
    middleware = _build_middleware(issuer_url=ISSUER_URL)
    request = _build_request(
        path="/rpc",
        authorization_header=authorization_header,
    )

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called for malformed bearer auth")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_request", '
        'error_description="Authorization header must use Bearer token"'
    )
