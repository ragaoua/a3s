import sys
import threading
import logging

import uvicorn

from src.agent import create_app
from src.config import load_config
from src.logging import setup_logging


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
    config = load_config()
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
