from ipaddress import IPv4Address
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
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


class OAuthJwtPoliciesConfig(StrictModel):
    jwks: OAuthDiscoveredJwksPolicyConfig | OAuthStaticJwksPolicyConfig
    rfc9068: OAuthRfc9068PolicyConfig | None = None
    claims: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)


class OAuthIntrospectionPolicyConfig(StrictModel):
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(min_length=1)
    auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        "client_secret_basic"
    )


class OAuthDiscoveredIntrospectionPolicyConfig(OAuthIntrospectionPolicyConfig):
    discovered: Literal[True] = True


class OAuthStaticIntrospectionPolicyConfig(OAuthIntrospectionPolicyConfig):
    discovered: Literal[False] = False
    endpoint: Url


class OAuthPoliciesConfig(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        # `"anyOf": ...` is necessary here to signal that at least one of jwt
        # or introspection must be set and not null. This is the JSON schema
        # transcription of the `validate_policies` method below.
        json_schema_extra={
            "anyOf": [
                {"required": ["jwt"], "properties": {"jwt": {"not": {"type": "null"}}}},
                {
                    "required": ["introspection"],
                    "properties": {"introspection": {"not": {"type": "null"}}},
                },
            ],
        },
    )

    jwt: OAuthJwtPoliciesConfig | None = None
    introspection: (
        OAuthDiscoveredIntrospectionPolicyConfig
        | OAuthStaticIntrospectionPolicyConfig
        | None
    ) = None

    @model_validator(mode="after")
    def validate_policies(self):
        if self.jwt is None and self.introspection is None:
            raise ValueError(
                "At least one of 'jwt' or 'introspection' must be configured"
            )

        return self


class OAuthConfig(StrictModel):
    mode: Literal["oauth2"] = "oauth2"
    issuer_url: Url
    policies: OAuthPoliciesConfig


class ApiKeyAuthConfig(StrictModel):
    mode: Literal["api_key"] = "api_key"
    api_key: SecretStr = Field(min_length=1)


class McpServerOAuthTokenForwardAuthConfig(StrictModel):
    mode: Literal["oauth_token_forward"] = "oauth_token_forward"


class McpServerOAuthClientAuthConfig(StrictModel):
    mode: Literal["oauth_token_exchange", "oauth_client_credentials"]
    token_endpoint: Url
    client_id: NonEmptyStr
    client_secret: SecretStr = Field(min_length=1)
    auth_method: Literal["client_secret_basic", "client_secret_post"] = (
        "client_secret_basic"
    )


class McpServerConfig(StrictModel):
    url: Url
    auth: (
        Literal["none"]
        | McpServerOAuthTokenForwardAuthConfig
        | McpServerOAuthClientAuthConfig
    )


class LoggingConfig(StrictModel):
    level: Literal["INFO", "DEBUG", "WARNING", "ERROR"] = "INFO"
    format: Literal["plain", "json"] = "plain"
