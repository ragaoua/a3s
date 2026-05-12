import logging


from src.config.types import LoggingConfig


def setup_logging(logging_config: LoggingConfig):
    logging.basicConfig(
        level=logging_config.level,
        format=(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
            if logging_config.format == "json"
            else "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        ),
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
