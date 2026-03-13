import os
import sys
from functools import lru_cache

from attr import dataclass
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.loggingManager import LoggingManager

logger = LoggingManager().get_logger(__name__)


@dataclass
class APIKeyAuth:
    api_key: str


@dataclass
class OAuth2Auth:
    oauth2_issuer_url: str
    oauth2_jwks_url: str | None


def _compute_auth() -> APIKeyAuth | OAuth2Auth:
    agent_api_key = os.getenv("AGENT_API_KEY")
    oauth2_issuer_url = os.getenv("OAUTH2_ISSUER_URL")
    if (agent_api_key is None) == (oauth2_issuer_url is None):
        raise ValueError(
            "Exactly one auth mode must be configured: set either AGENT_API_KEY to enable API Key auth, or OAUTH2_ISSUER_URL to enabled OAuth2 (but not both)"
        )

    if agent_api_key is not None:
        return APIKeyAuth(agent_api_key)

    assert oauth2_issuer_url is not None
    return OAuth2Auth(oauth2_issuer_url, oauth2_jwks_url=os.getenv("OAUTH2_JWKS_URL"))


def _compute_mcp_servers() -> list[str]:
    mcp_servers_raw = os.getenv("MCP_SERVERS") or ""
    return [item.strip() for item in mcp_servers_raw.split(",") if item.strip()]


class _Config(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True)

    llm_api_uri: str = Field(validation_alias="LLM_API_URI", init=False)
    llm_api_key: str = Field(validation_alias="LLM_API_KEY", init=False)
    model: str = Field(validation_alias="MODEL", init=False)
    agent_name: str = Field(validation_alias="AGENT_NAME", init=False)
    agent_description: str = Field(validation_alias="AGENT_DESCRIPTION", init=False)
    agent_instructions: str = Field(validation_alias="AGENT_INSTRUCTIONS", init=False)
    listen_port: int = Field(validation_alias="LISTEN_PORT", init=False)
    auth: APIKeyAuth | OAuth2Auth = Field(
        default_factory=_compute_auth,
        exclude=True,
        init=False,
    )
    mcp_servers: list[str] = Field(
        default_factory=_compute_mcp_servers,
        exclude=True,
        init=False,
    )


@lru_cache(maxsize=1)
def get_config() -> _Config:
    try:
        return _Config()
    except Exception as e:
        logger.debug("Failed to load config", exc_info=True)
        logger.error(e)
        sys.exit(1)
