from ipaddress import IPv4Address
from typing import Literal

from pydantic import Field

from src.config.types.common import StrictModel


class ServerConfig(StrictModel):
    listen_address: IPv4Address | Literal["localhost"] = IPv4Address("127.0.0.1")
    listen_port: int = Field(default=8000, ge=1, le=65535)
