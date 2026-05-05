from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from src.config.config import CONFIG_FILE_ENV_VAR_NAME, load_config


def _write_config(path: Path, body: str) -> None:
    path.write_text(dedent(body), encoding="utf-8")


def test_load_config_resolves_file_reads_yaml_substitutes_env_and_validates(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "agent.yaml"
    _write_config(
        config_file,
        """
        llm:
          api_url: http://example.com
          api_key: ${LLM_KEY}
          model: ${MODEL}
        agent:
          name: Cody
          description: A coding assistant
          instructions: Help the user.
        auth: none
        """,
    )

    env = {
        CONFIG_FILE_ENV_VAR_NAME: str(config_file),
        "LLM_KEY": "super-secret",
        "MODEL": "gpt-4o-mini",
    }

    config = load_config(env=env)

    assert config.llm.api_key.get_secret_value() == "super-secret"
    assert config.llm.model == "gpt-4o-mini"
    assert config.agent.name == "Cody"
    assert config.auth == "none"


def test_load_config_propagates_substitution_errors_for_missing_env(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "agent.yaml"
    _write_config(
        config_file,
        """
        llm:
          api_url: http://example.com
          api_key: ${LLM_KEY}
          model: m
        agent:
          name: a
          description: d
          instructions: i
        auth: none
        """,
    )

    env = {CONFIG_FILE_ENV_VAR_NAME: str(config_file)}

    with pytest.raises(ValidationError, match="LLM_KEY"):
        load_config(env=env)  # pyright: ignore[reportUnusedCallResult]


def test_load_config_propagates_schema_errors_for_invalid_config(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "agent.yaml"
    _write_config(
        config_file,
        """
        llm:
          api_url: http://example.com
          api_key: k
          model: m
        agent:
          name: a
          description: d
          instructions: i
        auth: none
        unknown_field: oops
        """,
    )

    env = {CONFIG_FILE_ENV_VAR_NAME: str(config_file)}

    with pytest.raises(ValidationError):
        load_config(env=env)  # pyright: ignore[reportUnusedCallResult]
