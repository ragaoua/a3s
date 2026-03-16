import os
import sys
from functools import lru_cache
from typing import Annotated, Self

from attr import dataclass
from pydantic import (
    Field,
    PrivateAttr,
    StringConstraints,
    ValidationError,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.loggingManager import LoggingManager

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

logger = LoggingManager().get_logger(__name__)


@dataclass
class APIKeyAuth:
    api_key: str


@dataclass
class OAuth2Auth:
    oauth2_issuer_url: str
    oauth2_jwks_url: str | None


def validate_auth_config(
    *,
    agent_api_key: str | None,
    oauth2_issuer_url: str | None,
    oauth2_jwks_url: str | None,
    no_auth: bool,
) -> APIKeyAuth | OAuth2Auth | None:
    has_api_key = bool(agent_api_key)
    has_oauth2 = bool(oauth2_issuer_url)
    auth_modes_configured = sum((has_api_key, has_oauth2, no_auth))

    if auth_modes_configured != 1:
        raise ValueError(
            "Exactly one auth mode must be configured:\n"
            + "set either AGENT_API_KEY to enable API Key auth, "
            + "or OAUTH2_ISSUER_URL to enable OAuth2 (but not both).\n"
            + "Set NO_AUTH to 1 or true to disable auth altogether."
        )

    if has_oauth2:
        assert oauth2_issuer_url is not None
        return OAuth2Auth(oauth2_issuer_url, oauth2_jwks_url)
    if has_api_key:
        assert agent_api_key is not None
        return APIKeyAuth(agent_api_key)
    return None


def compute_mcp_servers() -> list[str]:
    mcp_servers_raw = os.getenv("MCP_SERVERS") or ""
    return [item.strip() for item in mcp_servers_raw.split(",") if item.strip()]


class Config(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True)

    llm_api_uri: NonEmptyStr = Field(validation_alias="LLM_API_URI", init=False)
    llm_api_key: NonEmptyStr = Field(validation_alias="LLM_API_KEY", init=False)
    model: NonEmptyStr = Field(validation_alias="MODEL", init=False)
    agent_name: NonEmptyStr = Field(validation_alias="AGENT_NAME", init=False)
    agent_description: NonEmptyStr = Field(
        validation_alias="AGENT_DESCRIPTION", init=False
    )
    agent_instructions: NonEmptyStr = Field(
        validation_alias="AGENT_INSTRUCTIONS", init=False
    )
    listen_port: int = Field(validation_alias="LISTEN_PORT", init=False)

    agent_api_key: NonEmptyStr | None = Field(
        default=None, validation_alias="AGENT_API_KEY", exclude=True
    )
    oauth2_issuer_url: NonEmptyStr | None = Field(
        default=None, validation_alias="OAUTH2_ISSUER_URL", exclude=True
    )
    oauth2_jwks_url: NonEmptyStr | None = Field(
        default=None, validation_alias="OAUTH2_JWKS_URL", exclude=True
    )
    no_auth: bool = Field(default=False, validation_alias="NO_AUTH", exclude=True)

    _auth: APIKeyAuth | OAuth2Auth | None = PrivateAttr()
    _mcp_servers: list[str] = PrivateAttr(default_factory=compute_mcp_servers)

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

        if model:
            agent_api_key = model.agent_api_key
            oauth2_issuer_url = model.oauth2_issuer_url
            oauth2_jwks_url = model.oauth2_jwks_url
            no_auth = model.no_auth
        else:
            agent_api_key = os.getenv("AGENT_API_KEY")
            oauth2_issuer_url = os.getenv("OAUTH2_ISSUER_URL")
            oauth2_jwks_url = os.getenv("OAUTH2_JWKS_URL")
            no_auth = os.getenv("NO_AUTH", "").lower() in ["1", "true"]

        try:
            auth = validate_auth_config(
                agent_api_key=agent_api_key,
                oauth2_issuer_url=oauth2_issuer_url,
                oauth2_jwks_url=oauth2_jwks_url,
                no_auth=no_auth,
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
                        "NO_AUTH": no_auth,
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
def get_config() -> Config:
    try:
        return Config()
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
