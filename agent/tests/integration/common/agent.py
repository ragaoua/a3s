from collections.abc import Generator
from contextlib import contextmanager
from ipaddress import IPv4Address
import socket
import threading

from src.a2a import build_a2a_server
from src.config.types import AuthConfig, ServerConfig, SessionsConfig
from tests.common.a2a import A2aServerFixture
from tests.common.config import get_base_test_config
from tests.common.llm import LlmFixture


@contextmanager
def start_agent_server(
    *,
    auth_config: AuthConfig,
    mock_llm: LlmFixture,
    sessions_config: SessionsConfig | None = None,
) -> Generator[A2aServerFixture]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]

    config = get_base_test_config(
        llm=mock_llm.llm_config(),
        auth=auth_config,
        server=ServerConfig(
            listen_address=IPv4Address("127.0.0.1"),
            listen_port=port,
        ),
        sessions=sessions_config,
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
