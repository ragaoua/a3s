import sys
from functools import lru_cache
from typing import Annotated, Self

from attr import dataclass
from pydantic import (
    Field,
    PrivateAttr,
    StringConstraints,
    ValidationError,
    field_validator,
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


def normalize_mcp_servers(
    mcp_servers: list[str] | tuple[str, ...] | str | None,
) -> list[str]:
    if mcp_servers is None:
        return []
    if isinstance(mcp_servers, str):
        return [item.strip() for item in mcp_servers.split(",") if item.strip()]
    return [item.strip() for item in mcp_servers if item.strip()]


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        populate_by_name=True,
        enable_decoding=False,
    )

    LLM_API_URI: NonEmptyStr = Field()
    LLM_API_KEY: NonEmptyStr = Field()
    MODEL: NonEmptyStr = Field()

    AGENT_NAME: NonEmptyStr = Field()
    AGENT_DESCRIPTION: NonEmptyStr = Field()
    AGENT_INSTRUCTIONS: NonEmptyStr = Field()
    LISTEN_PORT: int = Field(default=8000)

    AGENT_API_KEY: NonEmptyStr | None = Field(default=None, exclude=True)
    OAUTH2_ISSUER_URL: NonEmptyStr | None = Field(default=None, exclude=True)
    OAUTH2_JWKS_URL: NonEmptyStr | None = Field(default=None, exclude=True)
    NO_AUTH: bool = Field(default=False, exclude=True)
    _auth: APIKeyAuth | OAuth2Auth | None = PrivateAttr()

    MCP_SERVERS: list[NonEmptyStr] = Field(default_factory=list)

    @field_validator("MCP_SERVERS", mode="before")
    @classmethod
    def parse_mcp_servers(cls, value):
        return normalize_mcp_servers(value)

    @property
    def AUTH(self):
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
            agent_api_key = model.AGENT_API_KEY
            oauth2_issuer_url = model.OAUTH2_ISSUER_URL
            oauth2_jwks_url = model.OAUTH2_JWKS_URL
            no_auth = model.NO_AUTH
        else:
            agent_api_key = data["AGENT_API_KEY"] if "AGENT_API_KEY" in data else None
            oauth2_issuer_url = (
                data["OAUTH2_ISSUER_URL"] if "OAUTH2_ISSUER_URL" in data else None
            )
            oauth2_jwks_url = (
                data["OAUTH2_JWKS_URL"] if "OAUTH2_JWKS_URL" in data else None
            )
            if "NO_AUTH" in data:
                no_auth_raw_value = data["NO_AUTH"]
                if isinstance(no_auth_raw_value, str):
                    no_auth = no_auth_raw_value.lower() in [
                        "1",
                        "true",
                    ]
                else:
                    no_auth = isinstance(no_auth_raw_value, bool) and no_auth_raw_value
            else:
                no_auth = False

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


@lru_cache(maxsize=1)
def from_env() -> Config:
    try:
        return Config()  # pyright: ignore[reportCallIssue]
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
