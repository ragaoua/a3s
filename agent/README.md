Install the environment:

```bash
uv sync
```

Create a `.env` file (see [.env.example](.env.example)) then run the a2a agent:

```bash
uv run a3s-agent
```

By default, the agent listens on `127.0.0.1:8000`. You can override this with
`LISTEN_ADDRESS` and `LISTEN_PORT`.

See it in action:

```bash
uv run pytest tests/integration/test_no_auth::test_agent_is_reachable_in_no_auth_mode
uv run pytest tests/integration/test_api_key_auth::test_agent_is_reachable_when_api_key_auth_is_enabled
```

Run tests:

```bash
uv run pytest -s
```

Build and run the image:

```bash
podman build -t agent .
podman run \
    --interactive \
    --tty \
    --rm \
    --name a3s \
    --env-file .env \
    --publish "$LISTEN_PORT":"$LISTEN_PORT" \
    localhost/a3s-agent
```

**Note**: for testing, use host.containers.internal instead of localhost
when connecting, from the container, to MCP servers hosted on the host
of the container.
