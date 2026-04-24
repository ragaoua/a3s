from typing import Literal
from pydantic_core import Url

from src.config.types.common import StrictModel
from src.config.types.outbound_auth import (
    OAuthClientCredentialsAuthConfig,
    OAuthDiscoveredTokenExchangeAuthConfig,
    OAuthStaticTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
)


class McpServerConfig(StrictModel):
    url: Url
    auth: (
        Literal["none"]
        | OAuthTokenForwardAuthConfig
        | OAuthClientCredentialsAuthConfig
        | OAuthDiscoveredTokenExchangeAuthConfig
        | OAuthStaticTokenExchangeAuthConfig
    )
