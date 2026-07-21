from collections.abc import Generator
from typing import Literal, Protocol

from pydantic import SecretStr
import pytest
from pydantic_core import Url

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth
from src.config.types import OAuthClientCredentialsAuthConfig
from src.utils import FetchJson


class BuildGrantAuth(Protocol):
    def __call__(
        self,
        auth_method: Literal[
            "client_secret_basic", "client_secret_post"
        ] = "client_secret_basic",
        *,
        fetch_json: FetchJson | None = None,
    ) -> OAuthClientCredentialsAuth: ...


@pytest.fixture(autouse=True)
def clear_access_token_cache() -> Generator[None, None, None]:
    OAuthClientCredentialsAuth._access_token_cache.clear()  # pyright: ignore[reportPrivateUsage]
    OAuthClientCredentialsAuth._access_token_cache_locks.clear()  # pyright: ignore[reportPrivateUsage]
    yield


@pytest.fixture
def build_auth() -> BuildGrantAuth:
    def _build(
        auth_method: Literal[
            "client_secret_basic", "client_secret_post"
        ] = "client_secret_basic",
        *,
        fetch_json: FetchJson | None = None,
    ) -> OAuthClientCredentialsAuth:
        return OAuthClientCredentialsAuth(
            server_url=Url("https://mcp.example"),
            server_auth_config=OAuthClientCredentialsAuthConfig(
                mode="oauth_client_credentials",
                token_endpoint=Url("https://issuer.example/oauth/token"),
                client_id="client-id",
                client_secret=SecretStr("client-secret"),
                auth_method=auth_method,
            ),
            **({"fetch_json": fetch_json} if fetch_json is not None else {}),
        )

    return _build
