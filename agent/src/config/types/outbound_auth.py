from typing import Literal

from pydantic import Field, SecretStr
from pydantic_core import Url

from src.config.types.common import NonEmptyStr, StrictModel


class OAuthTokenForwardAuthConfig(StrictModel):
    mode: Literal["oauth_token_forward"]


class OAuthClientAuthConfig(StrictModel):
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(min_length=1)
    auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        "client_secret_basic"
    )


class OAuthClientCredentialsAuthConfig(OAuthClientAuthConfig):
    mode: Literal["oauth_client_credentials"]
    token_endpoint: Url


class OAuthTokenExchangeAuthConfig(OAuthClientAuthConfig):
    mode: Literal["oauth_token_exchange"]


class OAuthDiscoveredTokenExchangeAuthConfig(OAuthTokenExchangeAuthConfig):
    discovered: Literal[True] = True


class OAuthStaticTokenExchangeAuthConfig(OAuthTokenExchangeAuthConfig):
    discovered: Literal[False] = False
    token_endpoint: Url


class OutboundApiKeyAuthConfig(StrictModel):
    mode: Literal["api_key"]
    api_key: SecretStr = Field(min_length=1)
