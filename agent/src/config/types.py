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


class OAuthRfc9068PolicyConfig(StrictModel):
    resource_server: NonEmptyStr


class OAuthDiscoveredIntrospectionPolicyConfig(StrictModel):
    discovered: Literal[True] = True
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(min_length=1)
    auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        "client_secret_basic"
    )


class OAuthStaticIntrospectionPolicyConfig(StrictModel):
    discovered: Literal[False] = False
    endpoint: Url
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(min_length=1)
    auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        "client_secret_basic"
    )


class OAuthPoliciesConfig(StrictModel):
    jwks: OAuthDiscoveredJwksPolicyConfig | OAuthStaticJwksPolicyConfig
    introspection: (
        OAuthDiscoveredIntrospectionPolicyConfig
        | OAuthStaticIntrospectionPolicyConfig
        | None
    ) = None
    rfc9068: OAuthRfc9068PolicyConfig | None = None
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
