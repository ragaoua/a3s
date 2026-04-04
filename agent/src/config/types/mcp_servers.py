from typing import Literal

from pydantic import Field, SecretStr
from pydantic_core import Url

from src.config.types.common import NonEmptyStr, StrictModel


class McpServerOAuthTokenForwardAuthConfig(StrictModel):
    mode: Literal["oauth_token_forward"]


class McpServerOAuthClientAuthConfig(StrictModel):
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(min_length=1)
    auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        "client_secret_basic"
    )


class McpServerOAuthClientCredentialsAuthConfig(McpServerOAuthClientAuthConfig):
    mode: Literal["oauth_client_credentials"] = "oauth_client_credentials"
    token_endpoint: Url


class McpServerOAuthTokenExchangeAuthConfig(McpServerOAuthClientAuthConfig):
    mode: Literal["oauth_token_exchange"] = "oauth_token_exchange"


class McpServerOAuthDiscoveredTokenExchangeAuthConfig(
    McpServerOAuthTokenExchangeAuthConfig
):
    discovered: Literal[True] = True


class McpServerOAuthStaticTokenExchangeAuthConfig(
    McpServerOAuthTokenExchangeAuthConfig
):
    discovered: Literal[False] = False
    token_endpoint: Url


class McpServerConfig(StrictModel):
    url: Url
    auth: (
        Literal["none"]
        | McpServerOAuthTokenForwardAuthConfig
        | McpServerOAuthClientCredentialsAuthConfig
        | McpServerOAuthDiscoveredTokenExchangeAuthConfig
        | McpServerOAuthStaticTokenExchangeAuthConfig
    )
