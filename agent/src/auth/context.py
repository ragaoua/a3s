from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


_CURRENT_AUTHORIZATION_HEADER: ContextVar[str | None] = ContextVar(
    "current_authorization_header",
    default=None,
)


def get_current_authorization_header() -> str | None:
    return _CURRENT_AUTHORIZATION_HEADER.get()


@contextmanager
def bind_current_authorization_header(
    authorization_header: str,
) -> Iterator[None]:
    token = _CURRENT_AUTHORIZATION_HEADER.set(authorization_header)
    try:
        yield
    finally:
        _CURRENT_AUTHORIZATION_HEADER.reset(token)
