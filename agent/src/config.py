import os
import sys
from functools import lru_cache
from typing import Self

from attr import dataclass
from pydantic import Field, PrivateAttr, ValidationError, model_validator
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


def _validate_auth_config(
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    oauth2_jwks_url: str | None,
) -> APIKeyAuth | OAuth2Auth:
    if (agent_api_key is None) == (oauth2_issuer_url is None):
        raise ValueError(
            "Exactly one auth mode must be configured: "
            + "set either AGENT_API_KEY to enable API Key auth, "
            + "or OAUTH2_ISSUER_URL to enabled OAuth2 (but not both)"
        )

    if agent_api_key is not None:
        return APIKeyAuth(agent_api_key)

    assert oauth2_issuer_url is not None
    return OAuth2Auth(oauth2_issuer_url, oauth2_jwks_url)


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

    agent_api_key: str | None = Field(
        default=None, validation_alias="AGENT_API_KEY", exclude=True
    )
    oauth2_issuer_url: str | None = Field(
        default=None, validation_alias="OAUTH2_ISSUER_URL", exclude=True
    )
    oauth2_jwks_url: str | None = Field(
        default=None, validation_alias="OAUTH2_JWKS_URL", exclude=True
    )

    _auth: APIKeyAuth | OAuth2Auth = PrivateAttr()
    _mcp_servers: list[str] = PrivateAttr(default_factory=_compute_mcp_servers)

    @property
    def auth(self):
        return self._auth

    @model_validator(mode="wrap")
    @classmethod
    def validate_auth(cls, data, handler):
        errors = []
        model: Self | None = None
        try:
            model = handler(data)
        except ValidationError as e:
            errors.extend(e.errors())

        agent_api_key = model.agent_api_key if model else os.getenv("AGENT_API_KEY")
        oauth2_issuer_url = (
            model.oauth2_issuer_url if model else os.getenv("OAUTH2_ISSUER_URL")
        )
        oauth2_jwks_url = (
            model.oauth2_jwks_url if model else os.getenv("OAUTH2_JWKS_URL")
        )
        try:
            auth = _validate_auth_config(
                agent_api_key, oauth2_issuer_url, oauth2_jwks_url
            )
            if model is not None:
                model._auth = auth
        except ValueError as e:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ("Auth",),
                    "input": {
                        "AGENT_API_KEY": agent_api_key,
                        "OAUTH2_ISSUER_URL": oauth2_issuer_url,
                    },
                    "ctx": {"error": e},
                }
            )
        if errors:
            raise ValidationError.from_exception_data(cls.__name__, errors)

        assert model is not None
        return model

    @property
    def mcp_servers(self):
        return self._mcp_servers


@lru_cache(maxsize=1)
def get_config() -> _Config:
    try:
        return _Config()
    except Exception as e:
        logger.debug("Failed to load config", exc_info=True)
        if isinstance(e, ValidationError):
            for error in e.errors(include_url=False):
                loc = error["loc"]
                msg = error["msg"]
                logger.error(f"{loc}: {msg}")
        else:
            logger.error(e)
        sys.exit(1)
