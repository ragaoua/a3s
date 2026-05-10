from datetime import datetime, timezone

import pytest

from src.auth.outbound import OAuthClientCredentialsAuth
from tests.unit.auth.outbound.utils import encode_jwt


@pytest.mark.parametrize(
    "expires_in",
    [60, 60.5, "60", "60.5"],
)
def test_get_access_token_expiry_date_uses_expires_in_when_present(
    expires_in: int | float | str,
) -> None:
    before = datetime.now(timezone.utc).timestamp()
    expiry = OAuthClientCredentialsAuth._get_access_token_expiry_date(
        {"expires_in": expires_in}, "ignored-token"
    )
    after = datetime.now(timezone.utc).timestamp()

    assert expiry is not None
    assert before + float(expires_in) <= expiry.timestamp() <= after + float(expires_in)


@pytest.mark.parametrize(
    "expires_in",
    [True, "not-a-number", None],
)
def test_get_access_token_expiry_date_falls_back_to_jwt_when_expires_in_is_invalid(
    expires_in: bool | str | None,
) -> None:
    expiry = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    token = encode_jwt({"exp": expiry.timestamp()})

    if expires_in is not None:
        assert (
            OAuthClientCredentialsAuth._get_access_token_expiry_date(
                {"expires_in": expires_in}, token
            )
            == expiry
        )
    else:
        assert (
            OAuthClientCredentialsAuth._get_access_token_expiry_date({}, token)
            == expiry
        )


def test_get_access_token_expiry_date_returns_none_for_jwt_without_expires_in() -> None:
    token = encode_jwt({"scope": "email profile"})
    assert OAuthClientCredentialsAuth._get_access_token_expiry_date({}, token) is None


def test_get_access_token_expiry_date_returns_none_for_non_jwt_without_expires_in() -> (
    None
):
    assert (
        OAuthClientCredentialsAuth._get_access_token_expiry_date({}, "not-a-jwt")
        is None
    )
