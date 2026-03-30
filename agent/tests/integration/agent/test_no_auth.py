import httpx
import pytest
from a2a.client import A2AClient

from tests.utils import get_base_test_config

from tests.integration.utils import (
    run_single_turn_test,
    start_agent_server,
    wait_for_agent_card,
)


@pytest.mark.asyncio
async def test_agent_is_reachable_in_no_auth_mode() -> None:
    config = get_base_test_config(auth="none")

    server, server_thread = start_agent_server(config)

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=10),
        ) as httpx_client:
            agent_url = (
                f"http://{config.server.listen_address}:{config.server.listen_port}"
            )
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
