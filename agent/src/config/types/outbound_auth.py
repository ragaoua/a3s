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


class BaseOAuthTokenExchangeAuthConfig(OAuthClientAuthConfig):
    mode: Literal["oauth_token_exchange"]


class OAuthDiscoveredTokenExchangeAuthConfig(BaseOAuthTokenExchangeAuthConfig):
    discovered: Literal[True] = True
    issuer_url: Url

    # Exclude issuer_url from the schema generated from self.model_json_schema:
    # when the token endpoint is "discovered", the issuer url shouldn't be user-defined.
    # Instead, it should be resolved as the value of top-level auth.issuer_url
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)

        schema["properties"].pop("issuer_url", None)
        if "required" in schema:
            schema["required"] = [x for x in schema["required"] if x != "issuer_url"]

        return schema


class OAuthStaticTokenExchangeAuthConfig(BaseOAuthTokenExchangeAuthConfig):
    discovered: Literal[False] = False
    token_endpoint: Url


class OutboundApiKeyAuthConfig(StrictModel):
    mode: Literal["api_key"]
    api_key: SecretStr = Field(min_length=1)


OAuthTokenExchangeAuthConfig = (
    OAuthDiscoveredTokenExchangeAuthConfig | OAuthStaticTokenExchangeAuthConfig
)
