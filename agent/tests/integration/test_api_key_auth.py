import httpx
import pytest
from a2a.client import A2AClient, A2AClientHTTPError

from src.auth import ApiKeyAuthMiddleware
from tests.integration.utils import (
    get_base_test_config_with,
    run_single_turn_test,
    start_agent_server,
    wait_for_agent_card,
)


@pytest.mark.asyncio
async def test_agent_sends_401_when_wrong_api_key_is_provided() -> None:

    config = get_base_test_config_with(AGENT_API_KEY="123")

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            headers={ApiKeyAuthMiddleware.HEADER_NAME: "abc"},
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = f"http://localhost:{config.LISTEN_PORT}"
            agent_card = await wait_for_agent_card(agent_url, httpx_client)
            print("--- 📇 Resolved agent card ---")
            print(agent_card.model_dump_json(indent=2, exclude_none=True))

            # Create a client to interact with the agent
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card,
            )

            with pytest.raises(A2AClientHTTPError) as exc:
                await run_single_turn_test(client)

            assert exc.value.status_code == 401

    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

        assert not server_thread.is_alive(), "Agent server thread failed to stop"


@pytest.mark.asyncio
async def test_agent_sends_401_when_no_api_key_is_provided() -> None:
    config = get_base_test_config_with(AGENT_API_KEY="123")

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = f"http://localhost:{config.LISTEN_PORT}"
            agent_card = await wait_for_agent_card(agent_url, httpx_client)
            print("--- 📇 Resolved agent card ---")
            print(agent_card.model_dump_json(indent=2, exclude_none=True))

            # Create a client to interact with the agent
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card,
            )

            with pytest.raises(A2AClientHTTPError) as exc:
                await run_single_turn_test(client)

            assert exc.value.status_code == 401

    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

        assert not server_thread.is_alive(), "Agent server thread failed to stop"


@pytest.mark.asyncio
async def test_agent_is_reachable_when_api_key_auth_is_enabled() -> None:
    config = get_base_test_config_with(AGENT_API_KEY="123")

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            headers={ApiKeyAuthMiddleware.HEADER_NAME: "123"},
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = f"http://localhost:{config.LISTEN_PORT}"
            agent_card = await wait_for_agent_card(agent_url, httpx_client)
            print("--- 📇 Resolved agent card ---")
            print(agent_card.model_dump_json(indent=2, exclude_none=True))

            # Create a client to interact with the agent
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=agent_card,
            )

            await run_single_turn_test(client)
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

        assert not server_thread.is_alive(), "Agent server thread failed to stop"
