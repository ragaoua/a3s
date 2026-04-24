from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


def get_access_token_expiry_date(
    token_response: dict[str, Any],
    token: str,
) -> datetime | None:
    expires_in_raw = token_response.get("expires_in")
    expires_in: int | float | None = None

    if isinstance(expires_in_raw, (int, float)):
        if not isinstance(expires_in_raw, bool):
            expires_in = expires_in_raw
    elif isinstance(expires_in_raw, str):
        try:
            expires_in = float(expires_in_raw)
        except ValueError:
            pass

    if expires_in is not None:
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # No expires_in key in the token response. Try and
    # decode the token as a JWT to fetch the "exp" claim
    try:
        return get_exp_datetime_from_jwt(token)
    except jwt.DecodeError:
        # Not a JWT, we can't know the expiry date.
        # We'll fallback to reactive token refreshing
        return None


def get_exp_datetime_from_jwt(token: str) -> datetime | None:
    payload = jwt.decode(token, options={"verify_signature": False})
    exp = payload.get("exp")

    if isinstance(exp, (int, float)):
        if isinstance(exp, bool):
            return None

        try:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(exp, str):
        return None

    try:
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
