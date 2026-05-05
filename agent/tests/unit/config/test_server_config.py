from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from src.config.types import ServerConfig


def test_server_config_defaults() -> None:
    config = ServerConfig()

    assert config.listen_address == IPv4Address("127.0.0.1")
    assert config.listen_port == 8000


@pytest.mark.parametrize("address", ["127.0.0.1", "0.0.0.0", "10.20.30.40"])
def test_server_config_accepts_ipv4_strings(address: str) -> None:
    config = ServerConfig(listen_address=IPv4Address(address))

    assert config.listen_address == IPv4Address(address)


def test_server_config_accepts_localhost_literal() -> None:
    config = ServerConfig(listen_address="localhost")

    assert config.listen_address == "localhost"


@pytest.mark.parametrize("invalid_address", ["::1", "not-an-ip", "256.0.0.1", ""])
def test_server_config_rejects_invalid_listen_address(invalid_address: str) -> None:
    with pytest.raises(ValidationError):
        ServerConfig(listen_address=invalid_address)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType, reportUnusedCallResult]


@pytest.mark.parametrize("port", [1, 8000, 65535])
def test_server_config_accepts_valid_listen_ports(port: int) -> None:
    assert ServerConfig(listen_port=port).listen_port == port


@pytest.mark.parametrize("port", [0, -1, 65536, 100000])
def test_server_config_rejects_out_of_range_listen_ports(port: int) -> None:
    with pytest.raises(ValidationError):
        ServerConfig(listen_port=port)  # pyright: ignore[reportUnusedCallResult]
