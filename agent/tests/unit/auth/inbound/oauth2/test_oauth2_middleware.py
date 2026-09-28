import time

import pytest
from authlib.jose import JsonWebKey, jwt
from pydantic import JsonValue, SecretStr
from pydantic_core import Url
from starlette.authentication import AuthCredentials, SimpleUser
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from src.auth.inbound.constants import EXCLUDED_PATHS
from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import OAuthRfc9068PolicyConfig
from src.utils import FetchJson
from tests.unit.auth.inbound.oauth2.fetch_json import route_fetch_json

ISSUER_URL = "https://issuer.example"
JWKS_URL = f"{ISSUER_URL}/jwks"
INTROSPECTION_URL = f"{ISSUER_URL}/introspect"

SIGNING_KEY_DICT: dict[str, str] = {
    "kty": "oct",
    "k": "GawgguFyGrWKav7AX4VKUg",
    "kid": "test",
}
OTHER_KEY_DICT: dict[str, str] = {
    "kty": "oct",
    "k": "OmFuZHRoZW5pY2FtZWFub3RoZXI",
    "kid": "test",
}
JWKS_PAYLOAD: dict[str, JsonValue] = {
    "keys": [
        {
            "kty": "oct",
            "k": "GawgguFyGrWKav7AX4VKUg",
            "kid": "test",
        }
    ]
}


def _encode(
    payload: dict[str, JsonValue],
    *,
    key_dict: dict[str, str] = SIGNING_KEY_DICT,
) -> str:
    header: dict[str, JsonValue] = {"alg": "HS256", "kid": "test"}
    key = JsonWebKey.import_key(key_dict)
    token: bytes = jwt.encode(header, payload, key)  # pyright: ignore[reportUnknownMemberType]
    return token.decode("ascii")


def _build_oauth_fetch_json(
    introspection_response: dict[str, JsonValue],
) -> FetchJson:
    return route_fetch_json(
        {
            JWKS_URL: JWKS_PAYLOAD,
            INTROSPECTION_URL: introspection_response,
        }
    )


def _introspection_config() -> OAuthStaticIntrospectionPolicyConfig:
    return OAuthStaticIntrospectionPolicyConfig(
        endpoint=Url(INTROSPECTION_URL),
        client_id="resource-server",
        client_secret=SecretStr("secret"),
    )


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


@pytest.mark.asyncio
async def test_dispatch_propagates_validate_token_failure() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    # Token is signed with a key that is NOT in the JWKS, so JWT validation fails.
    token = _encode(
        {"iss": ISSUER_URL, "exp": int(time.time()) + 3600},
        key_dict=OTHER_KEY_DICT,
    )
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when token validation fails")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == (
        'Bearer realm="test-realm", error="invalid_token", '
        'error_description="The access token is invalid"'
    )


@pytest.mark.asyncio
async def test_dispatch_calls_next_when_validate_token_succeeds() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    token = _encode({"iss": ISSUER_URL, "exp": int(time.time()) + 3600})
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    expected = JSONResponse({"ok": True}, status_code=200)

    async def call_next(_: Request) -> Response:
        return expected

    response = await middleware.dispatch(request, call_next)

    assert response is expected


@pytest.mark.asyncio
async def test_dispatch_sets_request_user_from_jwt_sub_claim() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    # A token validated by the plain JWT policy (no rfc9068) also carries a
    # trusted, signature-verified subject when `sub` is present.
    token = _encode(
        {"iss": ISSUER_URL, "exp": int(time.time()) + 3600, "sub": "user-123"}
    )
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    user = request.scope.get("user")
    assert isinstance(user, SimpleUser)
    assert user.is_authenticated
    assert user.display_name == "user-123"
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid"]


@pytest.mark.asyncio
async def test_dispatch_does_not_set_request_user_when_sub_is_missing_from_jwt() -> (
    None
):
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    token = _encode({"iss": ISSUER_URL, "exp": int(time.time()) + 3600})
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    assert "user" not in request.scope
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid"]


@pytest.mark.asyncio
async def test_dispatch_translates_scope_claim_into_auth_credentials() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    token = _encode(
        {
            "iss": ISSUER_URL,
            "exp": int(time.time()) + 3600,
            "sub": "user-123",
            "scope": "tasks:read tasks:write",
        },
    )
    request = _build_request(
        path="/rpc",
        authorization_header=f"Bearer {token}",
    )

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    user = request.scope.get("user")
    assert isinstance(user, SimpleUser)
    assert user.is_authenticated
    assert user.display_name == "user-123"
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid", "tasks:read", "tasks:write"]


@pytest.mark.asyncio
async def test_dispatch_sets_request_auth_when_scope_claim_is_present_but_not_identity_claim() -> (
    None
):
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    token = _encode(
        {
            "iss": ISSUER_URL,
            "exp": int(time.time()) + 3600,
            "scope": "tasks:read tasks:write",
        },
    )
    request = _build_request(
        path="/rpc",
        authorization_header=f"Bearer {token}",
    )

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    assert "user" not in request.scope
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid", "tasks:read", "tasks:write"]


@pytest.mark.asyncio
async def test_dispatch_sets_request_user_and_scopes_from_introspection() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        config=OAuthPoliciesConfig(introspection=_introspection_config()),
        fetch_json=_build_oauth_fetch_json(
            {
                "active": True,
                "sub": "introspected-user",
                "scope": "tasks:read tasks:write",
            }
        ),
    )
    request = _build_request(path="/rpc", authorization_header="Bearer opaque-token")

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    user = request.scope.get("user")
    assert isinstance(user, SimpleUser)
    assert user.display_name == "introspected-user"
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid", "tasks:read", "tasks:write"]


@pytest.mark.asyncio
async def test_dispatch_prefers_introspection_identity_and_scopes_over_jwt() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        config=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(JWKS_URL)),
            ),
            introspection=_introspection_config(),
        ),
        fetch_json=_build_oauth_fetch_json(
            {
                "active": True,
                "sub": "current-user",
                "scope": "current:scope",
            }
        ),
    )
    token = _encode(
        {
            "iss": ISSUER_URL,
            "sub": "jwt-user",
            "scope": "jwt:scope",
        }
    )
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    user = request.scope.get("user")
    assert isinstance(user, SimpleUser)
    assert user.display_name == "current-user"
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid", "current:scope"]


@pytest.mark.asyncio
async def test_dispatch_ignores_malformed_optional_introspection_claims() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        config=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(JWKS_URL)),
            ),
            introspection=_introspection_config(),
        ),
        fetch_json=_build_oauth_fetch_json(
            {
                "active": True,
                "sub": 123,
                "client_id": "introspection-client",
                "scope": ["invalid"],
            }
        ),
    )
    token = _encode(
        {
            "iss": ISSUER_URL,
            "sub": "jwt-user",
            "scope": "jwt:scope",
        }
    )
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    user = request.scope.get("user")
    assert isinstance(user, SimpleUser)
    assert user.display_name == "jwt-user"
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid", "jwt:scope"]


@pytest.mark.asyncio
async def test_dispatch_uses_namespaced_client_id_when_sub_is_absent() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        config=OAuthPoliciesConfig(introspection=_introspection_config()),
        fetch_json=_build_oauth_fetch_json(
            {"active": True, "client_id": "billing-worker"}
        ),
    )
    request = _build_request(path="/rpc", authorization_header="Bearer opaque-token")

    async def call_next(_: Request) -> Response:
        return JSONResponse({"ok": True}, status_code=200)

    _ = await middleware.dispatch(request, call_next)

    user = request.scope.get("user")
    assert isinstance(user, SimpleUser)
    assert user.display_name == "oauth-client:billing-worker"


@pytest.mark.asyncio
async def test_dispatch_accepts_introspected_token_without_identity_claims() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        config=OAuthPoliciesConfig(introspection=_introspection_config()),
        fetch_json=_build_oauth_fetch_json({"active": True}),
    )
    request = _build_request(path="/rpc", authorization_header="Bearer opaque-token")

    expected = JSONResponse({"ok": True}, status_code=200)

    async def call_next(_: Request) -> Response:
        return expected

    response = await middleware.dispatch(request, call_next)

    assert response is expected
    assert "user" not in request.scope
    auth = request.scope.get("auth")
    assert isinstance(auth, AuthCredentials)
    assert auth.scopes == ["token-valid"]


@pytest.mark.asyncio
async def test_dispatch_does_not_set_request_user_when_token_is_rejected() -> None:
    middleware = _build_middleware(
        issuer_url=ISSUER_URL,
        config=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
                rfc9068=OAuthRfc9068PolicyConfig(resource_server="rs"),
                claims={},
            )
        ),
        fetch_json=route_fetch_json({JWKS_URL: JWKS_PAYLOAD}),
    )
    token = _encode(
        {"iss": ISSUER_URL, "exp": int(time.time()) + 3600},
        key_dict=OTHER_KEY_DICT,
    )  # Lacks RFC-9068 mandatory claims like `sub`
    request = _build_request(path="/rpc", authorization_header=f"Bearer {token}")

    async def call_next(_: Request) -> Response:
        pytest.fail("call_next should not be called when token validation fails")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert "user" not in request.scope
    assert "auth" not in request.scope
