from datetime import datetime, timezone

from pydantic import JsonValue
import pytest

from src.auth.outbound import OAuthClientCredentialsAuth


def test_get_exp_datetime_from_jwt_returns_datetime_for_numeric_exp() -> None:
    expiry = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    payload: dict[str, JsonValue] = {"exp": expiry.timestamp()}

    assert (
        OAuthClientCredentialsAuth._get_exp_datetime_from_jwt_payload(payload) == expiry  # pyright: ignore[reportPrivateUsage]
    )


def test_get_exp_datetime_from_jwt_parses_string_exp() -> None:
    expiry = datetime.fromtimestamp(1_700_000_000.5, tz=timezone.utc)
    payload: dict[str, JsonValue] = {"exp": str(expiry.timestamp())}

    assert (
        OAuthClientCredentialsAuth._get_exp_datetime_from_jwt_payload(payload) == expiry  # pyright: ignore[reportPrivateUsage]
    )


@pytest.mark.parametrize(
    "exp", [True, None, [], {}, "not a datetime string", 999999999999]
)
def test_get_exp_datetime_from_jwt_returns_none_for_unsupported_exp_types(
    exp: JsonValue,
) -> None:
    payload: dict[str, JsonValue] = {"exp": exp}

    assert (
        OAuthClientCredentialsAuth._get_exp_datetime_from_jwt_payload(payload) is None  # pyright: ignore[reportPrivateUsage]
    )
