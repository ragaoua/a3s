from collections.abc import Iterable
from typing import Any

import pytest
from authlib.jose import JsonWebKey, KeySet, jwt
from authlib.jose.errors import InvalidClaimError, MissingClaimError

from src.auth.oauth2 import RFC9068AccessTokenValidator


ISSUER_URL = "https://issuer.example"
RESOURCE_SERVER = "api://agent"
_JWK_DICT = {
    "kty": "oct",
    "k": "c2VjcmV0c2VjcmV0c2VjcmV0c2VjcmV0",
    "kid": "test-key-id",
}


def _build_jwk_set() -> KeySet:
    return JsonWebKey.import_key_set({"keys": [_JWK_DICT]})


def _encode_access_token(*, claims: dict[str, Any], typ: str = "at+jwt") -> str:
    key = JsonWebKey.import_key(_JWK_DICT)
    token = jwt.encode({"alg": "HS256", "kid": "test-key-id", "typ": typ}, claims, key)
    return token.decode("utf-8")


def _default_claims(*, audience: str | Iterable[str]) -> dict[str, Any]:
    return {
        "iss": ISSUER_URL,
        "sub": "test-subject",
        "aud": audience,
        "exp": 9999999999,
        "iat": 1700000000,
        "jti": "test-jti",
        "client_id": "test-client-id",
    }


def test_get_jwks_returns_the_configured_key_set() -> None:
    jwk_set = _build_jwk_set()
    validator = RFC9068AccessTokenValidator(
        issuer=ISSUER_URL,
        resource_server=RESOURCE_SERVER,
        jwk_set=jwk_set,
    )

    assert validator.get_jwks() is jwk_set


def test_validate_accepts_a_rfc9068_access_token_for_the_configured_audience() -> None:
    token = _encode_access_token(claims=_default_claims(audience=[RESOURCE_SERVER]))
    validator = RFC9068AccessTokenValidator(
        issuer=ISSUER_URL,
        resource_server=RESOURCE_SERVER,
        jwk_set=_build_jwk_set(),
    )

    claims = validator.authenticate_token(token)
    claims.validate()

    assert claims["iss"] == ISSUER_URL
    assert claims["aud"] == [RESOURCE_SERVER]


def test_validate_rejects_a_non_access_token_type() -> None:
    token = _encode_access_token(
        claims=_default_claims(audience=[RESOURCE_SERVER]),
        typ="JWT",
    )
    validator = RFC9068AccessTokenValidator(
        issuer=ISSUER_URL,
        resource_server=RESOURCE_SERVER,
        jwk_set=_build_jwk_set(),
    )

    claims = validator.authenticate_token(token)

    with pytest.raises(InvalidClaimError, match="Invalid claim 'typ'"):
        claims.validate()


def test_validate_ignores_audience_when_resource_server_is_not_configured() -> None:
    token = _encode_access_token(
        claims=_default_claims(
            audience=["api://other"],
        ),
    )
    validator = RFC9068AccessTokenValidator(
        issuer=ISSUER_URL,
        resource_server=None,
        jwk_set=_build_jwk_set(),
    )

    claims = validator.authenticate_token(token)
    claims.validate()

    assert claims["aud"] == ["api://other"]


@pytest.mark.parametrize(
    "missing_claim",
    ["iss", "sub", "aud", "exp", "iat", "jti", "client_id"],
)
def test_validate_rejects_tokens_missing_required_rfc9068_claims(
    missing_claim: str,
) -> None:
    claims_payload = _default_claims(audience=[RESOURCE_SERVER])
    claims_payload.pop(missing_claim)

    token = _encode_access_token(claims=claims_payload)
    validator = RFC9068AccessTokenValidator(
        issuer=ISSUER_URL,
        resource_server=RESOURCE_SERVER,
        jwk_set=_build_jwk_set(),
    )

    claims = validator.authenticate_token(token)

    with pytest.raises(MissingClaimError, match=f"Missing '{missing_claim}' claim"):
        claims.validate()
