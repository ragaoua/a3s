import pytest
from pydantic import ValidationError

from src.config.types import PersistenceConfig


@pytest.mark.parametrize(
    "connect_string",
    [
        "postgresql://user:password@localhost:5432/agent",
        "postgres://user:password@localhost:5432/agent",
        "sqlite:///agent.db",
        "sqlite:///var/lib/a3s/agent.db",
        "sqlite:////var/lib/a3s/agent.db",
        "sqlite://",
        "sqlite:///:memory:",
    ],
)
def test_persistence_config_accepts_postgres_and_sqlite_connect_strings(
    connect_string: str,
) -> None:
    config = PersistenceConfig.model_validate({"connect_string": connect_string})

    assert str(config.connect_string.get_secret_value()) == connect_string


@pytest.mark.parametrize(
    "connect_string",
    [
        "",
        "localhost:5432/agent",
        "mysql://user:password@localhost:3306/agent",
        "postgresql+psycopg2://user:password@localhost:5432/agent",
        "postgresql+asyncpg://user:password@localhost:5432/agent",
        "sqlite+aiosqlite:///agent.db",
    ],
)
def test_persistence_config_rejects_unsupported_connect_strings(
    connect_string: str,
) -> None:
    with pytest.raises(ValidationError):
        PersistenceConfig.model_validate({"connect_string": connect_string})  # pyright: ignore[reportUnusedCallResult]


def test_persistence_config_does_not_leak_connect_string() -> None:
    config = PersistenceConfig.model_validate(
        {"connect_string": "postgresql://user:password@localhost:5432/agent"}
    )

    assert "password" not in repr(config)
    assert "password" not in str(config)
