import pytest
from pydantic import SecretStr, ValidationError
from pydantic_core import Url

from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticIntrospectionPolicyConfig,
)
from src.config.types.auth import OAuthDiscoveredJwksPolicyConfig


JWT_ONLY = OAuthJwtPolicyConfig(jwks=OAuthDiscoveredJwksPolicyConfig())
INTROSPECTION_ONLY = OAuthStaticIntrospectionPolicyConfig(
    client_id="c",
    client_secret=SecretStr("s"),
    endpoint=Url("http://idp.example.com/introspect"),
)


def test_validate_policies_rejects_when_neither_jwt_nor_introspection_set() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OAuthPoliciesConfig()  # pyright: ignore[reportUnusedCallResult]

    assert any(
        "At least one of 'jwt' or 'introspection' must be configured" in error["msg"]
        for error in exc_info.value.errors(include_url=False)
    )


def test_validate_policies_rejects_when_both_explicitly_none() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OAuthPoliciesConfig(jwt=None, introspection=None)  # pyright: ignore[reportUnusedCallResult]

    assert any(
        "At least one of 'jwt' or 'introspection' must be configured" in error["msg"]
        for error in exc_info.value.errors(include_url=False)
    )


def test_validate_policies_accepts_jwt_only() -> None:
    policies = OAuthPoliciesConfig(jwt=JWT_ONLY)

    assert policies.jwt is JWT_ONLY
    assert policies.introspection is None


def test_validate_policies_accepts_introspection_only() -> None:
    policies = OAuthPoliciesConfig(introspection=INTROSPECTION_ONLY)

    assert policies.jwt is None
    assert policies.introspection is INTROSPECTION_ONLY


def test_validate_policies_accepts_both() -> None:
    policies = OAuthPoliciesConfig(jwt=JWT_ONLY, introspection=INTROSPECTION_ONLY)

    assert policies.jwt is JWT_ONLY
    assert policies.introspection is INTROSPECTION_ONLY
