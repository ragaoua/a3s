"""A2A task-store persistence tests, parametrized over the database backends.

The task store is durable whenever the `persistence` connect string is set: A2A
`Task` records are written to the `tasks` table and can be read back by a fresh
server process. The in-memory default (no `persistence`) has no such guarantee,
which is exactly why these tests exercise only the database-backed store.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from a2a.types import GetTaskSuccessResponse
from src.config.types import PersistenceConfig
from tests.common.llm import LlmFixture
from tests.integration.common.agent import start_agent_server
from tests.integration.common.persistence import fetch_rows, get_task, send_message


@pytest.mark.asyncio
async def test_task_is_stored_in_database(
    mock_llm: LlmFixture,
    persistence_db_connect_string: str,
) -> None:
    persistence_config = PersistenceConfig.model_validate(
        {"connect_string": persistence_db_connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Hello from the mock LLM!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=persistence_config,
    ) as agent_server:
        task = await send_message(
            agent_server.base_url, text="hi", context_id=context_id
        )

    task_rows = await fetch_rows(
        persistence_config.connect_string.get_secret_value(),
        f"SELECT id, context_id FROM tasks WHERE id = '{task.id}'",
    )

    assert len(task_rows) == 1
    assert task_rows[0]["context_id"] == context_id


@pytest.mark.asyncio
async def test_task_db_backed_survives_server_restart(
    mock_llm: LlmFixture,
    persistence_db_connect_string: str,
) -> None:
    persistence_config = PersistenceConfig.model_validate(
        {"connect_string": persistence_db_connect_string}
    )
    context_id = uuid4().hex

    mock_llm.stub_response("Nice to meet you, Ada!")
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=persistence_config,
    ) as agent_server:
        task = await send_message(
            agent_server.base_url, text="My name is Ada.", context_id=context_id
        )

    # A fresh server process, sharing only the database, must still resolve the
    # task the previous process created — proof the task store read it back from
    # the persistent backend rather than in-process memory.
    with start_agent_server(
        auth_config="none",
        mock_llm=mock_llm,
        persistence_config=persistence_config,
    ) as agent_server:
        response = await get_task(agent_server.base_url, task.id)

    assert isinstance(response.root, GetTaskSuccessResponse)
    assert response.root.result.id == task.id
    assert response.root.result.context_id == context_id
