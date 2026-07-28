from typing import Literal

from src.config.types.common import StrictModel


class LoggingConfig(StrictModel):
    level: Literal["INFO", "DEBUG", "WARNING", "ERROR"] = "INFO"
    format: Literal["plain", "json"] = "plain"


class TracingConfig(StrictModel):
    enabled: bool = False


class ObservabilityConfig(StrictModel):
    logging: LoggingConfig = LoggingConfig()
    tracing: TracingConfig = TracingConfig()
