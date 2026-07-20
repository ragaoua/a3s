import pytest
from pydantic import ValidationError

from src.config.types import SessionsConfig


@pytest.mark.parametrize(
    "connect_string",
    [
        "postgresql://user:password@localhost:5432/sessions",
        "postgres://user:password@localhost:5432/sessions",
    ],
)
def test_sessions_config_accepts_postgres_connect_strings(connect_string: str) -> None:
    config = SessionsConfig.model_validate({"connect_string": connect_string})

    assert str(config.connect_string.get_secret_value()) == connect_string


@pytest.mark.parametrize(
    "connect_string",
    [
        "sqlite:///sessions.db",
        "sqlite:///var/lib/a3s/sessions.db",
        "sqlite:////var/lib/a3s/sessions.db",
        "sqlite://",
        "sqlite:///:memory:",
    ],
)
def test_sessions_config_accepts_sqlite_connect_strings(
    connect_string: str,
) -> None:
    config = SessionsConfig.model_validate({"connect_string": connect_string})

    assert str(config.connect_string.get_secret_value()) == connect_string


@pytest.mark.parametrize(
    "connect_string",
    [
        "",
        "localhost:5432/sessions",
        "mysql://user:password@localhost:3306/sessions",
        "postgresql+psycopg2://user:password@localhost:5432/sessions",
        "postgresql+asyncpg://user:password@localhost:5432/sessions",
        "sqlite+aiosqlite:///sessions.db",
    ],
)
def test_sessions_config_rejects_unsupported_connect_strings(
    connect_string: str,
) -> None:
    with pytest.raises(ValidationError):
        SessionsConfig.model_validate({"connect_string": connect_string})  # pyright: ignore[reportUnusedCallResult]


def test_sessions_config_does_not_leak_connect_string() -> None:
    config = SessionsConfig.model_validate(
        {"connect_string": "postgresql://user:password@localhost:5432/sessions"}
    )

    assert "password" not in repr(config)
    assert "password" not in str(config)
