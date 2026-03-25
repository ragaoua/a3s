import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

JSON_FORMAT = '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
PLAIN_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
MODULE_LOGGERS = ("src.auth", "src.config", "src.agent", "uvicorn.error")
AGENT_ROOT = Path(__file__).resolve().parents[2]
PROBE_SCRIPT = """
import json
import logging

import src.main

root_logger = logging.getLogger()
print(
    json.dumps(
        {
            "root_level": root_logger.level,
            "handler_count": len(root_logger.handlers),
            "formatter": (
                root_logger.handlers[0].formatter._fmt
                if root_logger.handlers and root_logger.handlers[0].formatter
                else None
            ),
            "module_levels": {
                logger_name: logging.getLogger(logger_name).getEffectiveLevel()
                for logger_name in ("src.auth", "src.config", "src.agent", "uvicorn.error")
            },
        }
    )
)
"""


def _run_logging_probe(
    *,
    log_level: str,
    log_format: str,
) -> dict[str, object]:
    env = os.environ.copy()
    env["LOG_LEVEL"] = log_level
    env["LOG_FORMAT"] = log_format

    result = subprocess.run(
        [sys.executable, "-c", PROBE_SCRIPT],
        capture_output=True,
        check=True,
        cwd=AGENT_ROOT,
        env=env,
        text=True,
    )

    output_lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert output_lines, "The logging probe did not produce output"
    return json.loads(output_lines[-1])


@pytest.mark.parametrize(
    ("log_level", "expected_level", "log_format", "expected_format"),
    [
        ("DEBUG", logging.DEBUG, "json", JSON_FORMAT),
        ("ERROR", logging.ERROR, "plain", PLAIN_FORMAT),
    ],
)
def test_logging_configuration_is_propagated_to_imported_app_modules(
    log_level: str,
    expected_level: int,
    log_format: str,
    expected_format: str,
) -> None:
    result = _run_logging_probe(log_level=log_level, log_format=log_format)

    assert result["root_level"] == expected_level
    assert result["handler_count"] >= 1
    assert result["formatter"] == expected_format

    module_levels = result["module_levels"]
    assert isinstance(module_levels, dict)
    for module_name in MODULE_LOGGERS:
        assert module_levels[module_name] == expected_level
