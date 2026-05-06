from pathlib import Path

import pytest

from src.config.config import read_yaml_config
from tests.unit.config.utils import write_config


def test_read_yaml_config_raises_when_file_doesnt_exist(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.yaml"
    with pytest.raises(ValueError):
        read_yaml_config(missing_file)  # pyright: ignore[reportUnusedCallResult]


def test_read_yaml_config_returns_parsed_mapping(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    write_config(
        config_file,
        """
        llm:
            model: gpt-4o-mini
        agent:
            name: Cody
        """,
    )

    assert read_yaml_config(config_file) == {
        "llm": {"model": "gpt-4o-mini"},
        "agent": {"name": "Cody"},
    }


def test_read_yaml_config_raises_for_non_mapping_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    write_config(
        config_file,
        """
        - item
        - other
        """,
    )

    with pytest.raises(ValueError):
        read_yaml_config(config_file)  # pyright: ignore[reportUnusedCallResult]


def test_read_yaml_config_raises_for_malformed_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    write_config(
        config_file,
        """
        foo: [unclosed
        """,
    )

    with pytest.raises(ValueError, match="Error while parsing YAML file"):
        read_yaml_config(config_file)  # pyright: ignore[reportUnusedCallResult]


def test_read_yaml_config_raises_for_empty_file(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    write_config(config_file, "")

    with pytest.raises(ValueError, match="Invalid YAML"):
        read_yaml_config(config_file)  # pyright: ignore[reportUnusedCallResult]


def test_read_yaml_config_raises_for_scalar_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "agent.yaml"
    write_config(config_file, "42")

    with pytest.raises(ValueError, match="Invalid YAML"):
        read_yaml_config(config_file)  # pyright: ignore[reportUnusedCallResult]
