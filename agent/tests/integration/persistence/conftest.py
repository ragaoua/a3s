from pathlib import Path

import pytest

from tests.integration.common.session_service_db import SessionServiceDbFixture


@pytest.fixture(params=["postgres", "sqlite"])
def persistence_db_connect_string(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> str:
    if request.param == "postgres":
        db: SessionServiceDbFixture = request.getfixturevalue("session_service_db")
        return db.connect_string
    return f"sqlite:///{tmp_path / 'agent.db'}"
