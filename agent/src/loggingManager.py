import logging
import os
import sys
import threading
from typing import ClassVar, Self, final


@final
class LoggingManager:
    instance: ClassVar[Self | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls):
        if cls.instance is None:
            with cls._lock:
                if cls.instance is None:
                    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
                    log_format = os.getenv("LOG_FORMAT", "text").lower()
                    handler = logging.StreamHandler(sys.stdout)
                    if log_format == "json":
                        formatter = logging.Formatter(
                            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
                        )
                    else:
                        formatter = logging.Formatter(
                            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
                        )
                    handler.setFormatter(formatter)
                    root_logger = logging.getLogger()
                    root_logger.setLevel(log_level)
                    root_logger.addHandler(handler)

                    cls.instance = super().__new__(cls)

        return cls.instance

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)
