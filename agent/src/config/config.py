import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    ConfigDict,
    ValidationError,
    model_validator,
)
from pydantic_core import InitErrorDetails
from yaml.parser import ParserError

from src.config.constants import (
    CONFIG_FILE_ENV_VAR_NAME,
    DEFAULT_CONFIG_FILE,
)
from src.config.types import (
    AgentConfig,
    ApiKeyAuthConfig,
    LlmConfig,
    LoggingConfig,
    McpServerOAuthTokenForwardAuthConfig,
    McpServerConfig,
    McpServerOAuthClientAuthConfig,
    OAuthConfig,
    ServerConfig,
    StrictModel,
)

# matches ${var}
ENV_VAR_PATTERN = re.compile(r"^\$\{([^}]+)\}$")


def substitute_env_vars(config: dict[str, Any]) -> dict[str, Any]:
    """
    By design, only values that fully match `${VAR}` are substituted;
    strings that merely contain `${VAR}` are left unchanged.
    """
    errors: list[InitErrorDetails] = []

    def _resolve(value: Any, path: tuple[str | int, ...]) -> Any:
        if isinstance(value, dict):
            return {k: _resolve(v, (*path, k)) for k, v in value.items()}
        if isinstance(value, list):
            return [_resolve(item, (*path, index)) for index, item in enumerate(value)]
        if isinstance(value, str):
            match = ENV_VAR_PATTERN.fullmatch(value)
            if not match:
                return value

            env_var_name = match.group(1)
            substituted_value = os.environ.get(env_var_name)
            if substituted_value is None or substituted_value == "":
                errors.append(
                    {
                        "type": "value_error",
                        "loc": path,
                        "input": value,
                        "ctx": {
                            "error": ValueError(
                                f"Environment variable '{env_var_name}' is not set or empty"
                            )
                        },
                    }
                )
                return value
            return substituted_value
        return value

    resolved_config = _resolve(config, ())

    if errors:
        raise ValidationError.from_exception_data("Config", errors)

    return resolved_config


class Config(StrictModel):
    model_config = ConfigDict(
        title="A3S Agent Config",
        extra="forbid",
        # `"allOf": ...` is necessary here to signal that if one MCP Server is
        # configured with `auth` set to a `mode` that requires an oauth token,
        # the root-level `auth.mode` should be set to oauth2. This is the JSON
        # schema transcription of the `validate_policies` model validator
        # method below.
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "required": ["mcp_servers"],
                        "properties": {
                            "mcp_servers": {
                                "contains": {
                                    "type": "object",
                                    "required": ["auth"],
                                    "properties": {
                                        "auth": {
                                            "type": "object",
                                            "required": ["mode"],
                                            "properties": {
                                                "mode": {
                                                    "enum": [
                                                        "oauth_token_forward",
                                                        "oauth_token_exchange",
                                                    ]
                                                }
                                            },
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "then": {
                        "properties": {
                            "auth": {
                                "type": "object",
                                "required": ["mode"],
                                "properties": {
                                    "mode": {"const": "oauth2", "type": "string"}
                                },
                            }
                        }
                    },
                }
            ]
        },
    )

    llm: LlmConfig
    agent: AgentConfig
    server: ServerConfig = ServerConfig()
    auth: OAuthConfig | ApiKeyAuthConfig | Literal["none"]
    mcp_servers: list[McpServerConfig] = list()
    logging: LoggingConfig = LoggingConfig()

    @model_validator(mode="after")
    def validate_mcp_server_auth_requires_oauth2(self):
        if isinstance(self.auth, OAuthConfig):
            return self

        for index, serverConfig in enumerate(self.mcp_servers):
            if serverConfig.auth != "none" and (
                serverConfig.auth.mode
                in ["oauth_token_forward", "oauth_token_exchange"]
            ):
                raise ValueError(
                    f"`mcp_servers[{index}].auth.mode` '{serverConfig.auth.mode}' requires root-level `auth.mode: 'oauth2'`"
                )

        return self


def resolve_config_file() -> Path:
    raw_value = os.environ.get(CONFIG_FILE_ENV_VAR_NAME)
    if raw_value is not None:
        stripped_value = raw_value.strip()
        if stripped_value != "":
            return Path(stripped_value)

    return DEFAULT_CONFIG_FILE


def read_yaml_config(config_file: Path) -> dict[str, Any]:
    if not config_file.exists():
        raise ValueError(f"File not found: {config_file}")

    try:
        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Error while parsing YAML file {config_file}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML in {config_file}")

    return data


def load_config() -> Config:
    config_file = resolve_config_file()
    config_dict = read_yaml_config(config_file)
    config_dict = substitute_env_vars(config_dict)
    return Config.model_validate(config_dict)
