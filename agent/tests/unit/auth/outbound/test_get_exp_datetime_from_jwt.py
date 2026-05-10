from datetime import datetime, timezone

import pytest

from src.auth.outbound import OAuthClientCredentialsAuth
from tests.unit.auth.outbound.utils import encode_jwt


def test_get_exp_datetime_from_jwt_returns_datetime_for_numeric_exp() -> None:
    expiry = datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    token = encode_jwt({"exp": expiry.timestamp()})

    assert OAuthClientCredentialsAuth._get_exp_datetime_from_jwt(token) == expiry


def test_get_exp_datetime_from_jwt_parses_string_exp() -> None:
    expiry = datetime.fromtimestamp(1_700_000_000.5, tz=timezone.utc)
    token = encode_jwt({"exp": str(expiry.timestamp())})

    assert OAuthClientCredentialsAuth._get_exp_datetime_from_jwt(token) == expiry


@pytest.mark.parametrize("exp", [True, None, [], {}])
def test_get_exp_datetime_from_jwt_returns_none_for_unsupported_exp_types(
    exp: object,
) -> None:
    token = encode_jwt({"exp": exp})

    assert OAuthClientCredentialsAuth._get_exp_datetime_from_jwt(token) is None
