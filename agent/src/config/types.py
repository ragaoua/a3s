from ipaddress import IPv4Address
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
)
from pydantic_core import Url

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LlmConfig(StrictModel):
    api_url: Url
    api_key: SecretStr = Field(min_length=1)
    model: NonEmptyStr


class AgentConfig(StrictModel):
    name: NonEmptyStr
    description: NonEmptyStr
    instructions: NonEmptyStr


class ServerConfig(StrictModel):
    listen_address: IPv4Address | Literal["localhost"] = IPv4Address("127.0.0.1")
    listen_port: int = Field(default=8000, ge=1, le=65535)


class OAuthDiscoveredJwksPolicyConfig(StrictModel):
    discovered: Literal[True] = True


class OAuthStaticJwksPolicyConfig(StrictModel):
    discovered: Literal[False] = False
    url: Url


class OAuthEnabledRfc9068PolicyConfig(StrictModel):
    enabled: Literal[True] = True
    resource_server: NonEmptyStr


class OAuthDisabledRfc9068PolicyConfig(StrictModel):
    enabled: Literal[False] = False


class OAuthPoliciesConfig(StrictModel):
    jwks: OAuthDiscoveredJwksPolicyConfig | OAuthStaticJwksPolicyConfig
    rfc9068: OAuthEnabledRfc9068PolicyConfig | OAuthDisabledRfc9068PolicyConfig = (
        OAuthDisabledRfc9068PolicyConfig()
    )
    claims: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)


class OAuthConfig(StrictModel):
    mode: Literal["oauth2"] = "oauth2"
    issuer_url: Url
    policies: OAuthPoliciesConfig


class ApiKeyAuthConfig(StrictModel):
    mode: Literal["api_key"] = "api_key"
    api_key: SecretStr = Field(min_length=1)


class LoggingConfig(StrictModel):
    level: Literal["INFO", "DEBUG", "WARNING", "ERROR"] = "INFO"
    format: Literal["plain", "json"] = "plain"
