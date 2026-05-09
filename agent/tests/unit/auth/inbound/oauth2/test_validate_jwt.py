import time

from authlib.jose import JsonWebKey, jwt
from pydantic import JsonValue
import pytest
from pydantic_core import Url
from returns.result import Failure, Success
from starlette.types import Receive, Scope, Send

from src.auth.inbound.oauth2 import OAuth2BearerAuthMiddleware
from src.config.types import (
    OAuthJwtPolicyConfig,
    OAuthPoliciesConfig,
    OAuthStaticJwksPolicyConfig,
)
from src.config.types.auth import OAuthRfc9068PolicyConfig

ISSUER_URL = "https://issuer.example"
RESOURCE_SERVER = "rs"

SIGNING_KEY_DICT: dict[str, str] = {
    "kty": "oct",
    "k": "GawgguFyGrWKav7AX4VKUg",
    "kid": "test",
}
OTHER_KEY_DICT: dict[str, str] = {
    "kty": "oct",
    "k": "OmFuZHRoZW5pY2FtZWFub3RoZXI",
    "kid": "test",
}
JW_KEY_SET = JsonWebKey.import_key_set({"keys": [SIGNING_KEY_DICT]})


def _encode(
    payload: dict[str, JsonValue],
    *,
    header_extras: dict[str, JsonValue] | None = None,
    key_dict: dict[str, str] = SIGNING_KEY_DICT,
) -> str:
    header: dict[str, JsonValue] = {"alg": "HS256", "kid": "test"}
    if header_extras:
        header.update(header_extras)
    key = JsonWebKey.import_key(key_dict)
    token: bytes = jwt.encode(header, payload, key)  # pyright: ignore[reportUnknownMemberType]
    return token.decode("ascii")


def _build_middleware() -> OAuth2BearerAuthMiddleware:
    async def app(_scope: Scope, _receive: Receive, _send: Send):
        return None

    return OAuth2BearerAuthMiddleware(
        app=app,
        issuer_url=ISSUER_URL,
        realm="test-realm",
        config=OAuthPoliciesConfig(
            jwt=OAuthJwtPolicyConfig(
                jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
                rfc9068=None,
                claims={},
            )
        ),
    )


def _base_jwt_config(
    *,
    rfc9068: OAuthRfc9068PolicyConfig | None = None,
    claims: dict[str, str] | None = None,
) -> OAuthJwtPolicyConfig:
    return OAuthJwtPolicyConfig(
        jwks=OAuthStaticJwksPolicyConfig(url=Url(f"{ISSUER_URL}/jwks")),
        rfc9068=rfc9068,
        claims=claims or {},
    )


def _rfc9068_payload(*, exp_offset: int = 3600) -> dict[str, JsonValue]:
    now = int(time.time())
    return {
        "iss": ISSUER_URL,
        "exp": now + exp_offset,
        "iat": now,
        "sub": "user",
        "aud": RESOURCE_SERVER,
        "client_id": "client",
        "jti": "jti-1",
    }


def test_returns_success_for_valid_base_jwt() -> None:
    middleware = _build_middleware()
    token = _encode({"iss": ISSUER_URL, "exp": int(time.time()) + 3600})

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token, jwt_config=_base_jwt_config(), jwk_set=JW_KEY_SET
    )

    assert isinstance(res, Success)


def test_returns_failure_when_token_is_expired() -> None:
    middleware = _build_middleware()
    token = _encode({"iss": ISSUER_URL, "exp": int(time.time()) - 60})

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token, jwt_config=_base_jwt_config(), jwk_set=JW_KEY_SET
    )

    assert isinstance(res, Failure)
    assert res.failure() == "The access token expired"


def test_returns_failure_when_issuer_does_not_match() -> None:
    middleware = _build_middleware()
    token = _encode({"iss": "https://other.example", "exp": int(time.time()) + 3600})

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token, jwt_config=_base_jwt_config(), jwk_set=JW_KEY_SET
    )

    assert isinstance(res, Failure)
    assert res.failure() == "The access token is invalid"


def test_returns_failure_when_signature_is_invalid() -> None:
    middleware = _build_middleware()
    token = _encode(
        {"iss": ISSUER_URL, "exp": int(time.time()) + 3600},
        key_dict=OTHER_KEY_DICT,
    )

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token, jwt_config=_base_jwt_config(), jwk_set=JW_KEY_SET
    )

    assert isinstance(res, Failure)
    assert res.failure() == "The access token is invalid"


def test_returns_success_for_valid_rfc9068_token() -> None:
    middleware = _build_middleware()
    token = _encode(_rfc9068_payload(), header_extras={"typ": "at+jwt"})

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token,
        jwt_config=_base_jwt_config(
            rfc9068=OAuthRfc9068PolicyConfig(resource_server=RESOURCE_SERVER)
        ),
        jwk_set=JW_KEY_SET,
    )

    assert isinstance(res, Success)


def test_returns_failure_when_rfc9068_required_claim_is_missing() -> None:
    middleware = _build_middleware()
    payload = _rfc9068_payload()
    del payload["aud"]
    token = _encode(payload, header_extras={"typ": "at+jwt"})

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token,
        jwt_config=_base_jwt_config(
            rfc9068=OAuthRfc9068PolicyConfig(resource_server=RESOURCE_SERVER)
        ),
        jwk_set=JW_KEY_SET,
    )

    assert isinstance(res, Failure)
    assert res.failure() == "The access token is invalid"


def test_returns_failure_when_rfc9068_audience_does_not_match() -> None:
    middleware = _build_middleware()
    payload = _rfc9068_payload()
    payload["aud"] = "other-rs"
    token = _encode(payload, header_extras={"typ": "at+jwt"})

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token,
        jwt_config=_base_jwt_config(
            rfc9068=OAuthRfc9068PolicyConfig(resource_server=RESOURCE_SERVER)
        ),
        jwk_set=JW_KEY_SET,
    )

    assert isinstance(res, Failure)
    assert res.failure() == "The access token is invalid"


@pytest.mark.parametrize(
    "actual_value",
    ["wrong-tenant", None],
    ids=["mismatch", "missing"],
)
def test_returns_failure_when_required_custom_claim_is_missing_or_mismatched(
    actual_value: str | None,
) -> None:
    middleware = _build_middleware()
    payload: dict[str, JsonValue] = {"iss": ISSUER_URL, "exp": int(time.time()) + 3600}
    if actual_value is not None:
        payload["tenant"] = actual_value
    token = _encode(payload)

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token,
        jwt_config=_base_jwt_config(claims={"tenant": "acme"}),
        jwk_set=JW_KEY_SET,
    )

    assert isinstance(res, Failure)
    assert res.failure() == "The access token is invalid"


def test_returns_success_when_required_custom_claim_matches() -> None:
    middleware = _build_middleware()
    token = _encode(
        {
            "iss": ISSUER_URL,
            "exp": int(time.time()) + 3600,
            "tenant": "acme",
        }
    )

    res = middleware._validate_jwt(  # pyright: ignore[reportPrivateUsage]
        token,
        jwt_config=_base_jwt_config(claims={"tenant": "acme"}),
        jwk_set=JW_KEY_SET,
    )

    assert isinstance(res, Success)
