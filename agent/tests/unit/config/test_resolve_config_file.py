from pathlib import Path

import pytest

from src.config.config import (
    CONFIG_FILE_ENV_VAR_NAME,
    DEFAULT_CONFIG_FILE,
    resolve_config_file,
)


@pytest.mark.parametrize("raw_path", [None, "", "   "])
def test_resolve_config_file_returns_default_when_env_var_missing_or_blank(
    raw_path: str | None,
) -> None:
    env: dict[str, str] = {} if raw_path is None else {CONFIG_FILE_ENV_VAR_NAME: raw_path}

    assert resolve_config_file(env=env) == DEFAULT_CONFIG_FILE


def test_resolve_config_file_strips_surrounding_whitespace(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    env = {CONFIG_FILE_ENV_VAR_NAME: f"  {config_file}  "}

    assert resolve_config_file(env=env) == config_file
