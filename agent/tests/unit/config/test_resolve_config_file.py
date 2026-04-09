from pathlib import Path

import pytest

from src.config.config import resolve_config_file
from src.config.config import CONFIG_FILE_ENV_VAR_NAME, DEFAULT_CONFIG_FILE


@pytest.mark.parametrize("raw_path", [None, "", "   "])
def test_resolve_config_file_returns_default_when_env_var_missing_or_blank(
    monkeypatch: pytest.MonkeyPatch,
    raw_path: str | None,
) -> None:
    if raw_path is None:
        monkeypatch.delenv(CONFIG_FILE_ENV_VAR_NAME, raising=False)
    else:
        monkeypatch.setenv(CONFIG_FILE_ENV_VAR_NAME, raw_path)

    assert resolve_config_file() == DEFAULT_CONFIG_FILE


def test_resolve_config_file_strips_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "agent.yaml"
    monkeypatch.setenv(CONFIG_FILE_ENV_VAR_NAME, f"  {config_file}  ")

    assert resolve_config_file() == config_file
