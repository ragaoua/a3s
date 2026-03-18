import uvicorn
from .agent import create_app
from .config import from_env


def main() -> None:
    config = from_env()
    app = create_app(config)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=str(config.LISTEN_ADDRESS),
            port=config.LISTEN_PORT,
        )
    )
    server.run()


if __name__ == "__main__":
    main()
