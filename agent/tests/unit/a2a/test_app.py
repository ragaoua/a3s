from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.a2a import app as app_module
from src.config.types import PersistenceConfig, ServerConfig


@pytest.mark.asyncio
async def test_lifespan_closes_request_handler_and_database_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_session_service = Mock()
    database_session_service.db_engine = Mock()
    database_session_service.close = AsyncMock()
    request_handler = Mock()
    request_handler.aclose = AsyncMock()

    database_session_service_factory = Mock(return_value=database_session_service)
    task_store_factory = Mock(return_value=Mock())
    monkeypatch.setattr(
        app_module, "DatabaseSessionService", database_session_service_factory
    )
    monkeypatch.setattr(app_module, "DatabaseTaskStore", task_store_factory)
    monkeypatch.setattr(
        app_module, "DefaultRequestHandler", Mock(return_value=request_handler)
    )

    app = app_module.build_agent_a2a_app(
        agent=SimpleNamespace(  # type: ignore[arg-type]
            name="Cody", description="Coding assistant"
        ),
        server_config=ServerConfig(),
        auth_config="none",
        persistence_config=PersistenceConfig.model_validate(
            {"connect_string": "sqlite:///agent.db"}
        ),
    )

    async with app.router.lifespan_context(app):
        task_store_factory.assert_called_once_with(
            engine=database_session_service.db_engine
        )

    request_handler.aclose.assert_awaited_once_with()
    database_session_service.close.assert_awaited_once_with()
