from datetime import datetime, timezone

import jwt
import pytest

from src.auth.outbound.internal.token_helpers import (
    get_access_token_expiry_date,
    get_exp_datetime_from_jwt,
)


def _encode_jwt(payload: dict[str, object]) -> str:
    return jwt.encode(payload, key="", algorithm="none")


@pytest.mark.parametrize(
    "expires_in",
    [60, 60.5, "60", "60.5"],
)
def test_get_access_token_expiry_date_uses_expires_in_when_present(
    expires_in: int | float | str,
) -> None:
    before = datetime.now(timezone.utc).timestamp()
    expiry = get_access_token_expiry_date({"expires_in": expires_in}, "ignored-token")
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
    token = _encode_jwt({"exp": expiry.timestamp()})

    if expires_in is not None:
        assert get_access_token_expiry_date({"expires_in": expires_in}, token) == expiry
    else:
        assert get_access_token_expiry_date({}, token) == expiry


def test_get_access_token_expiry_date_returns_none_for_jwt_without_expires_in() -> None:
    token = _encode_jwt({"scope": "email profile"})
    assert get_access_token_expiry_date({}, token) is None


def test_get_access_token_expiry_date_returns_none_for_non_jwt_without_expires_in() -> (
    None
):
    assert get_access_token_expiry_date({}, "not-a-jwt") is None


def test_get_exp_datetime_from_jwt_returns_datetime_for_numeric_exp() -> None:
    expiry = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    token = _encode_jwt({"exp": expiry.timestamp()})

    assert get_exp_datetime_from_jwt(token) == expiry


def test_get_exp_datetime_from_jwt_parses_string_exp() -> None:
    expiry = datetime.fromtimestamp(1_700_000_000.5, tz=timezone.utc)
    token = _encode_jwt({"exp": str(expiry.timestamp())})

    assert get_exp_datetime_from_jwt(token) == expiry


@pytest.mark.parametrize("exp", [True, None, [], {}])
def test_get_exp_datetime_from_jwt_returns_none_for_unsupported_exp_types(
    exp: object,
) -> None:
    token = _encode_jwt({"exp": exp})

    assert get_exp_datetime_from_jwt(token) is None
