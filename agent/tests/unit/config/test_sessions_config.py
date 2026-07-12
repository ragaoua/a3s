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
        "",
        "localhost:5432/sessions",
        "mysql://user:password@localhost:3306/sessions",
        "sqlite:///sessions.db",
        "postgresql+psycopg2://user:password@localhost:5432/sessions",
        "postgresql+asyncpg://user:password@localhost:5432/sessions",
    ],
)
def test_sessions_config_rejects_non_postgres_connect_strings(
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
