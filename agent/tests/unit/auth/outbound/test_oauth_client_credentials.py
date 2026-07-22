from collections.abc import Generator

import httpx
import pytest
from pydantic import JsonValue, SecretStr
from pydantic_core import Url

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth
from src.auth.outbound.types import AccessTokenInfo
from src.config.types import OAuthClientCredentialsAuthConfig
from src.utils import FetchJson, fetch_json as _default_fetch_json


@pytest.fixture(autouse=True)
def clear_access_token_cache() -> Generator[None, None, None]:
    OAuthClientCredentialsAuth._access_token_cache.clear()  # pyright: ignore[reportPrivateUsage]
    OAuthClientCredentialsAuth._access_token_cache_locks.clear()  # pyright: ignore[reportPrivateUsage]
    yield


def _build_auth(
    *,
    fetch_json: FetchJson = _default_fetch_json,
) -> OAuthClientCredentialsAuth:
    return OAuthClientCredentialsAuth(
        server_url=Url("https://mcp.example"),
        server_auth_config=OAuthClientCredentialsAuthConfig(
            mode="oauth_client_credentials",
            token_endpoint=Url("https://issuer.example/oauth/token"),
            client_id="client-id",
            client_secret=SecretStr("client-secret"),
            auth_method="client_secret_basic",
        ),
        fetch_json=fetch_json,
    )


@pytest.mark.asyncio
async def test_request_token_propagates_fetch_json_error() -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,
        error_message: str | None = None,
    ) -> dict[str, JsonValue]:
        raise error_cls(error_message)

    auth = _build_auth(fetch_json=fetch_json)

    with pytest.raises(
        ValueError,
        match="Failed to fetch OAuth2 access token for server 'https://mcp.example/'",
    ):
        _ = await auth._request_token()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_request_token_returns_token_with_none_expiry_when_expires_in_missing() -> (
    None
):
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": "token-123"}

    auth = _build_auth(fetch_json=fetch_json)

    token_info = await auth._request_token()  # pyright: ignore[reportPrivateUsage]

    assert token_info == AccessTokenInfo("token-123", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("access_token", [None, "", 123])
async def test_request_token_rejects_invalid_access_token_type(
    access_token: JsonValue,
) -> None:
    async def fetch_json(
        url: str | httpx.Request,  # pyright: ignore[reportUnusedParameter]
        *,
        error_cls: type[Exception] = ValueError,  # pyright: ignore[reportUnusedParameter]
        error_message: str | None = None,  # pyright: ignore[reportUnusedParameter]
    ) -> dict[str, JsonValue]:
        return {"access_token": access_token}

    auth = _build_auth(fetch_json=fetch_json)

    with pytest.raises(
        ValueError,
        match="missing a valid 'access_token'",
    ):
        _ = await auth._request_token()  # pyright: ignore[reportPrivateUsage]
