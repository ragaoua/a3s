from typing import Literal

from pydantic import Field, PrivateAttr, SecretStr, computed_field
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

    # When the token endpoint is "discovered", the issuer URL is never
    # user-defined: it is resolved from the top-level auth.issuer_url by the
    # Config after-validator (see Config._resolve_outbound_oauth2_issuer_url),
    # which calls resolve_issuer_url().
    #
    # It is stored as a private attribute so it stays out of the (validation)
    # input schema -- a user cannot set it -- and exposed as a computed field so
    # consumers get a non-optional Url and it still appears in model_dump().
    _issuer_url: Url | None = PrivateAttr(default=None)

    def resolve_issuer_url(self, issuer_url: Url) -> None:
        self._issuer_url = issuer_url

    @computed_field
    @property
    def issuer_url(self) -> Url:
        if self._issuer_url is None:
            raise RuntimeError(
                "issuer_url accessed before it was resolved from the root auth config"
            )
        return self._issuer_url


class OAuthStaticTokenExchangeAuthConfig(BaseOAuthTokenExchangeAuthConfig):
    discovered: Literal[False] = False
    token_endpoint: Url


class OutboundApiKeyAuthConfig(StrictModel):
    mode: Literal["api_key"]
    api_key: SecretStr = Field(min_length=1)


OAuthTokenExchangeAuthConfig = (
    OAuthDiscoveredTokenExchangeAuthConfig | OAuthStaticTokenExchangeAuthConfig
)
