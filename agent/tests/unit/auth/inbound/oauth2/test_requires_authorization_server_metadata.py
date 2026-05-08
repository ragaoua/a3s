import pytest
from pydantic import SecretStr
from pydantic_core import Url
from starlette.types import Receive, Scope, Send

from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import (
    OAuthDiscoveredIntrospectionPolicyConfig,
    OAuthDiscoveredJwksPolicyConfig,
)

ISSUER_URL = "https://issuer.example"

STATIC_JWKS = OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks"))
DISCOVERED_JWKS = OAuthDiscoveredJwksPolicyConfig()

STATIC_INTROSPECTION = OAuthStaticIntrospectionPolicyConfig(
    client_id="client",
    client_secret=SecretStr("secret"),
    endpoint=Url(f"{ISSUER_URL}/introspect"),
)
DISCOVERED_INTROSPECTION = OAuthDiscoveredIntrospectionPolicyConfig(
    client_id="client",
    client_secret=SecretStr("secret"),
)


def _build_middleware(*, config: OAuthPoliciesConfig) -> OAuth2BearerAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=config,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        # jwt only
        (
            OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS, rfc9068=None, claims={}),
            ),
            False,
        ),
        (
            OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(
                    jwks=DISCOVERED_JWKS, rfc9068=None, claims={}
                ),
            ),
            True,
        ),
        # introspection only
        (
            OAuthPoliciesConfig(introspection=STATIC_INTROSPECTION),
            False,
        ),
        (
            OAuthPoliciesConfig(introspection=DISCOVERED_INTROSPECTION),
            True,
        ),
        # jwt + introspection combinations
        (
            OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS, rfc9068=None, claims={}),
                introspection=STATIC_INTROSPECTION,
            ),
            False,
        ),
        (
            OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(jwks=STATIC_JWKS, rfc9068=None, claims={}),
                introspection=DISCOVERED_INTROSPECTION,
            ),
            True,
        ),
        (
            OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(
                    jwks=DISCOVERED_JWKS, rfc9068=None, claims={}
                ),
                introspection=STATIC_INTROSPECTION,
            ),
            True,
        ),
        (
            OAuthPoliciesConfig(
                jwt=OAuthJwtPolicyConfig(
                    jwks=DISCOVERED_JWKS, rfc9068=None, claims={}
                ),
                introspection=DISCOVERED_INTROSPECTION,
            ),
            True,
        ),
    ],
    ids=[
        "jwt-static",
        "jwt-discovered",
        "introspection-static",
        "introspection-discovered",
        "jwt-static+introspection-static",
        "jwt-static+introspection-discovered",
        "jwt-discovered+introspection-static",
        "jwt-discovered+introspection-discovered",
    ],
)
def test_requires_authorization_server_metadata(
    config: OAuthPoliciesConfig, expected: bool
) -> None:
    middleware = _build_middleware(config=config)

    assert middleware._requires_authorization_server_metadata() is expected  # pyright: ignore[reportPrivateUsage]
