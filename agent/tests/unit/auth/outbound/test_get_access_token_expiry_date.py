from datetime import datetime, timezone

import jwt
from pydantic import JsonValue
import pytest

from src.auth.outbound.token_expiry import get_access_token_expiry_date


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
    [True, "not-a-number", None, [], {}],
)
def test_get_access_token_expiry_date_falls_back_to_jwt_when_expires_in_is_invalid_or_missing(
    expires_in: JsonValue,
) -> None:
    expiry = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    token = _encode_jwt({"exp": expiry.timestamp()})
    token_response: dict[str, JsonValue] = (
        {"expires_in": expires_in} if expires_in is not None else {}
    )

    assert get_access_token_expiry_date(token_response, token) == expiry


def test_get_access_token_expiry_date_returns_none_for_jwt_without_expires_in() -> None:
    token = _encode_jwt({"scope": "email profile"})
    assert get_access_token_expiry_date({}, token) is None


def test_get_access_token_expiry_date_returns_none_for_non_jwt_without_expires_in() -> (
    None
):
    assert get_access_token_expiry_date({}, "not-a-jwt") is None
