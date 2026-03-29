from pathlib import Path

import pytest

from src.config.config import read_yaml_config


def test_read_yaml_config_raises_when_file_doesnt_exist(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.yaml"
    with pytest.raises(ValueError):
        read_yaml_config(missing_file)  # pyright: ignore[reportUnusedCallResult]


def test_read_yaml_config_returns_parsed_mapping(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    config_file.write_text(  # pyright: ignore[reportUnusedCallResult]
        "llm:\n  model: gpt-4o-mini\nagent:\n  name: Cody\n",
        encoding="utf-8",
    )

    assert read_yaml_config(config_file) == {
        "llm": {"model": "gpt-4o-mini"},
        "agent": {"name": "Cody"},
    }


def test_read_yaml_config_raises_for_non_mapping_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    config_file.write_text("- item\n- other\n", encoding="utf-8")  # pyright: ignore[reportUnusedCallResult]

    with pytest.raises(ValueError):
        read_yaml_config(config_file)  # pyright: ignore[reportUnusedCallResult]
