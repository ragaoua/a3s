import pytest

from src.a2a.app import _sqlalchemy_db_url
from src.config.types import SessionsConfig


@pytest.mark.parametrize(
    "connect_string",
    [
        "postgresql://user:password@localhost:5432/sessions",
        "postgres://user:password@localhost:5432/sessions",
    ],
)
def test_sqlalchemy_db_url_normalizes_to_asyncpg(connect_string: str) -> None:
    config = SessionsConfig.model_validate({"connect_string": connect_string})

    db_url = _sqlalchemy_db_url(config)

    assert db_url == "postgresql+asyncpg://user:password@localhost:5432/sessions"


@pytest.mark.parametrize(
    ("connect_string", "expected"),
    [
        ("sqlite:///sessions.db", "sqlite+aiosqlite:///sessions.db"),
        (
            "sqlite:////var/lib/a3s/sessions.db",
            "sqlite+aiosqlite:////var/lib/a3s/sessions.db",
        ),
    ],
)
def test_sqlalchemy_db_url_normalizes_to_aiosqlite(
    connect_string: str, expected: str
) -> None:
    config = SessionsConfig.model_validate({"connect_string": connect_string})

    db_url = _sqlalchemy_db_url(config)

    assert db_url == expected
