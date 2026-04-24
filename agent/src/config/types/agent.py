from typing import Literal

from pydantic import Field
from pydantic_core import Url

from src.config.types.outbound_auth import (
    OAuthClientCredentialsAuthConfig,
    OAuthDiscoveredTokenExchangeAuthConfig,
    OAuthStaticTokenExchangeAuthConfig,
    OAuthTokenForwardAuthConfig,
    OutboundApiKeyAuthConfig,
)
from src.config.types.common import NonEmptyStr, StrictModel


class SubagentConfig(StrictModel):
    url: Url
    type: Literal["delegate", "peer"]
    auth: (
        Literal["none"]
        | OAuthTokenForwardAuthConfig
        | OAuthClientCredentialsAuthConfig
        | OAuthDiscoveredTokenExchangeAuthConfig
        | OAuthStaticTokenExchangeAuthConfig
        | OutboundApiKeyAuthConfig
    )


class AgentConfig(StrictModel):
    name: NonEmptyStr
    description: NonEmptyStr
    instructions: NonEmptyStr
    subagents: dict[NonEmptyStr, SubagentConfig] = Field(default_factory=dict)
    skills_dir: NonEmptyStr = "config/skills"
