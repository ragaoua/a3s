import sys
import threading
import logging

from pydantic import ValidationError
import uvicorn

from src.config import load_config
from src.observability.logging import setup_logging
from src.observability.telemetry import telemetry_instrumentation


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

    with telemetry_instrumentation(config):
        # NOTE: Lazily import build_a2a_server, inside the telemetry context.
        # The StarletteInstrumentor set up by telemetry_instrumentation()
        # patches in inbound-request tracing by swapping the class that
        # `starlette.applications.Starlette` points to.
        # `src.a2a.app` (which is imported by `src.a2a.server`) binds that name
        # at import time via `from starlette.applications import Starlette`, so
        # it only picks up the instrumented class if it's imported AFTER the
        # swap.
        # Hoisting this to a top-level import would bind the un-instrumented
        # class and silently drop all server-side request spans.
        from src.a2a import build_a2a_server

        server = build_a2a_server(config)

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
