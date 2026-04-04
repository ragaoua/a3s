from typing import Literal

from pydantic import ConfigDict, Field, SecretStr, model_validator
from pydantic_core import Url

from src.config.types.common import NonEmptyStr, StrictModel


class OAuthDiscoveredJwksPolicyConfig(StrictModel):
    discovered: Literal[True] = True


class OAuthStaticJwksPolicyConfig(StrictModel):
    discovered: Literal[False] = False
    url: Url


class OAuthRfc9068PolicyConfig(StrictModel):
    resource_server: NonEmptyStr


class OAuthJwtPolicyConfig(StrictModel):
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

    jwt: OAuthJwtPolicyConfig | None = None
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
