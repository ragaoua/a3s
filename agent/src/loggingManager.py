import logging
import threading
from typing import ClassVar, Literal, Self, final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingConfig(BaseSettings):
    """Bootstrap-only logging settings loaded independently from `Config`.

    Logging is initialized before the main application settings are validated.
    Keeping these fields in a separate settings model prevents logger setup from
    failing when unrelated required `Config` fields are missing or invalid.
    This just feel like a safer approach than putting the logging config in the
    global `Config` class.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        populate_by_name=True,
        extra="ignore",
    )

    LOG_LEVEL: Literal["INFO", "DEBUG", "WARNING", "ERROR"] = Field(default="INFO")
    LOG_FORMAT: Literal["plain", "json"] = Field(default="plain")


@final
class LoggingManager:
    _instance: ClassVar[Self | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logging_config = LoggingConfig()

                    logging.basicConfig(
                        level=logging_config.LOG_LEVEL,
                        format=(
                            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
                            if logging_config.LOG_FORMAT == "json"
                            else "%(asctime)s %(levelname)s [%(name)s] %(message)s"
                        ),
                        force=True,
                    )

                    cls._instance = super().__new__(cls)

        return cls._instance

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)
