import pytest
from authlib.jose import KeySet
from pydantic import SecretStr
from pydantic_core import Url
from starlette.types import Receive, Scope, Send

from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredIntrospectionPolicyConfig,
    OAuthDiscoveredJwksPolicyConfig,
    OAuthStaticIntrospectionPolicyConfig,
)
from src.utils import FetchJson


ISSUER_URL = "https://issuer.example"


def _build_middleware(
    *,
    config: OAuthPoliciesConfig,
    fetch_json: FetchJson | None = None,
) -> OAuth2BearerAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=config,
        **({"fetch_json": fetch_json} if fetch_json is not None else {}),
    )


def _static_jwt_config() -> OAuthPoliciesConfig:
    return OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(
            jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
            rfc9068=None,
            claims={},
        ),
    )


def _discovered_jwt_config() -> OAuthPoliciesConfig:
    return OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(
            jwks=OAuthDiscoveredJwksPolicyConfig(),
            rfc9068=None,
            claims={},
        ),
    )


def _static_introspection_config() -> OAuthPoliciesConfig:
    return OAuthPoliciesConfig(
        introspection=OAuthStaticIntrospectionPolicyConfig(
            endpoint=Url(f"{ISSUER_URL}/introspect"),
            client_id="c",
            client_secret=SecretStr("s"),
        )
    )


def _discovered_introspection_config() -> OAuthPoliciesConfig:
    return OAuthPoliciesConfig(
        introspection=OAuthDiscoveredIntrospectionPolicyConfig(
            client_id="c",
            client_secret=SecretStr("s"),
        )
    )


@pytest.mark.asyncio
async def test_fetch_jwk_set_uses_static_url_without_discovery() -> None:
    captured_urls: list[str] = []

    async def fetch_json(url, *, error_cls=ValueError, error_message=None):
        captured_urls.append(url)
        return {"keys": []}

    config = _static_jwt_config()
    middleware = _build_middleware(config=config, fetch_json=fetch_json)
    assert config.jwt is not None

    jwk_set = await middleware._fetch_jwk_set(jwtPolicyConfig=config.jwt)

    assert isinstance(jwk_set, KeySet)
    assert captured_urls == [f"{ISSUER_URL}/jwks"]


def test_requires_metadata_false_for_jwt_static_only() -> None:
    middleware = _build_middleware(config=_static_jwt_config())
    assert middleware._requires_authorization_server_metadata() is False


def test_requires_metadata_true_for_jwt_discovered() -> None:
    middleware = _build_middleware(config=_discovered_jwt_config())
    assert middleware._requires_authorization_server_metadata() is True


def test_requires_metadata_false_for_introspection_static_only() -> None:
    middleware = _build_middleware(config=_static_introspection_config())
    assert middleware._requires_authorization_server_metadata() is False


def test_requires_metadata_true_for_introspection_discovered() -> None:
    middleware = _build_middleware(config=_discovered_introspection_config())
    assert middleware._requires_authorization_server_metadata() is True


def test_requires_metadata_true_when_either_policy_needs_discovery() -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(
            jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
            rfc9068=None,
            claims={},
        ),
        introspection=OAuthDiscoveredIntrospectionPolicyConfig(
            client_id="c",
            client_secret=SecretStr("s"),
        ),
    )
    middleware = _build_middleware(config=config)
    assert middleware._requires_authorization_server_metadata() is True


def test_requires_metadata_false_when_both_policies_are_static() -> None:
    config = OAuthPoliciesConfig(
        jwt=OAuthJwtPolicyConfig(
            jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
            rfc9068=None,
            claims={},
        ),
        introspection=OAuthStaticIntrospectionPolicyConfig(
            endpoint=Url(f"{ISSUER_URL}/introspect"),
            client_id="c",
            client_secret=SecretStr("s"),
        ),
    )
    middleware = _build_middleware(config=config)
    assert middleware._requires_authorization_server_metadata() is False
