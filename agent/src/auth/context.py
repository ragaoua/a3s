from contextvars import ContextVar, Token


_CURRENT_AUTHORIZATION_HEADER: ContextVar[str | None] = ContextVar(
    "current_authorization_header",
    default=None,
)


def get_current_authorization_header() -> str | None:
    return _CURRENT_AUTHORIZATION_HEADER.get()


def set_current_authorization_header(
    authorization_header: str,
) -> Token[str | None]:
    return _CURRENT_AUTHORIZATION_HEADER.set(authorization_header)


def reset_current_authorization_header(token: Token[str | None]) -> None:
    _CURRENT_AUTHORIZATION_HEADER.reset(token)
