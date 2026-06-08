import socket
import threading
from collections.abc import Iterator
from ipaddress import IPv4Address
from pathlib import Path

import pytest

from src.a2a.server import build_a2a_server
from src.config.types import AgentConfig, ServerConfig
from tests.common.llm import LlmFixture
from tests.common.a2a import A2aServerFixture
from tests.common.config import get_base_test_config, write_skill


@pytest.fixture
def a2a_server(mock_llm: LlmFixture, tmp_path: Path) -> Iterator[A2aServerFixture]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]

    config = get_base_test_config(
        llm=mock_llm.llm_config(),
        agent=AgentConfig(
            name="Cody",
            description="A helpful coding assistant",
            instructions="You are a coding agent.",
            skills_dir=str(tmp_path),
        ),
        auth="none",
        server=ServerConfig(
            listen_address=IPv4Address("127.0.0.1"),
            listen_port=port,
        ),
    )

    write_skill(
        tmp_path,
        "hello-skill",
        description="says hello in a friendly tone",
        body="Greet the user warmly and ask how their day is going.",
    )

    server = build_a2a_server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        yield A2aServerFixture(
            base_url=f"http://127.0.0.1:{port}",
            mock_llm=mock_llm,
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
