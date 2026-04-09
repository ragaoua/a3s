from typing import Literal
from pydantic import SecretStr
from pydantic_core import Url
from ipaddress import IPv4Address
from src.config import Config
from src.config.types import (
    AgentConfig,
    ApiKeyAuthConfig,
    LlmConfig,
    McpServerConfig,
    OAuthConfig,
    ServerConfig,
)


def get_base_test_config(
    *,
    llm: LlmConfig = LlmConfig(
        api_url=Url("http://example.com"),
        api_key=SecretStr("fakekey"),
        model="mymodel",
    ),
    agent: AgentConfig = AgentConfig(
        name="Cody",
        description="A helpful coding assistant",
        instructions="You are a coding agent. Use the tools provided to access the user's requests regarding coding tasks",
    ),
    auth: OAuthConfig | ApiKeyAuthConfig | Literal["none"] = "none",
    server: ServerConfig = ServerConfig(
        listen_port=12345,
        listen_address=IPv4Address("127.0.0.1"),
    ),
    mcp_servers: list[McpServerConfig] = list(),
) -> Config:
    return Config(
        llm=llm,
        agent=agent,
        auth=auth,
        server=server,
        mcp_servers=mcp_servers,
    )
