import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
)
from pydantic_core import InitErrorDetails, Url

from src.config.constants import (
    CONFIG_FILE_ENV_VAR_NAME,
    DEFAULT_CONFIG_FILE,
)
from src.config.types import (
    AgentConfig,
    ApiKeyAuthConfig,
    LlmConfig,
    LoggingConfig,
    OAuthConfig,
    ServerConfig,
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


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: LlmConfig
    agent: AgentConfig
    server: ServerConfig = ServerConfig()
    auth: OAuthConfig | ApiKeyAuthConfig | Literal["none"]
    mcp_servers: list[Url] = list()
    logging: LoggingConfig = LoggingConfig()


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

    data = yaml.safe_load(config_file.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML in {config_file}")

    return data


def load_config() -> Config:
    config_file = resolve_config_file()
    config_dict = read_yaml_config(config_file)
    config_dict = substitute_env_vars(config_dict)
    return Config.model_validate(config_dict)
