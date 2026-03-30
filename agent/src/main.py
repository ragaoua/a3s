import sys
import threading
import logging

from pydantic import ValidationError
import uvicorn

from src.agent import create_app
from src.config import load_config
from src.logging import setup_logging


# We're not using LoggingManager because it
# depends on the config which we haven't yet loaded
logger = logging.getLogger(__name__)


def _watch_stdin_for_quit(server: uvicorn.Server) -> None:
    try:
        for line in sys.stdin:
            if line.strip().lower() == "q":
                server.should_exit = True
                return
    except Exception:
        # If stdin is not interactive/available, just continue without
        # command-based shutdown.
        return


def main() -> None:
    try:
        config = load_config()
    except (ValidationError, ValueError) as e:
        logging.basicConfig(level="ERROR")
        if isinstance(e, ValidationError):
            for error in e.errors(include_url=False):
                logging.error("%s: %s", ".".join(map(str, error["loc"])), error["msg"])
        else:
            logging.error(e)
        raise SystemExit(1)

    setup_logging(config.logging)
    app = create_app(config)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=str(config.server.listen_address),
            port=config.server.listen_port,
        )
    )

    quit_watcher = threading.Thread(
        target=_watch_stdin_for_quit,
        args=(server,),
        daemon=True,
    )
    quit_watcher.start()

    try:
        logger.info('Type "q" and press Enter to quit the server.')
        server.run()
    except KeyboardInterrupt:
        server.should_exit = True


if __name__ == "__main__":
    main()
