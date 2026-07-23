from datetime import datetime, timedelta, timezone

import jwt
from pydantic import JsonValue


def get_access_token_expiry_date(
    token_response: dict[str, JsonValue],
    token: str,
) -> datetime | None:
    """Best-effort expiry for an OAuth2 access token.

    Prefers the `expires_in` field from the token response; falls back to the
    `exp` claim if the token is a JWT. Returns None when neither is available,
    in which case callers fall back to reactive (401-driven) refreshing.
    """
    expires_in = token_response.get("expires_in")

    if isinstance(expires_in, (int, float)):
        if not isinstance(expires_in, bool):
            return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    elif isinstance(expires_in, str):
        try:
            return datetime.now(timezone.utc) + timedelta(seconds=float(expires_in))
        except ValueError:
            pass

    # No expires_in key in the token response. Try and decode the token as a
    # JWT to fetch the "exp" claim.
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except jwt.DecodeError:
        # Not a JWT, we can't know the expiry date.
        # We'll fall back to reactive token refreshing.
        return None

    return get_exp_datetime_from_jwt_payload(payload)


def get_exp_datetime_from_jwt_payload(
    payload: dict[str, JsonValue],
) -> datetime | None:
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
