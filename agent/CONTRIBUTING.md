# Contributing

## Running tests

```bash
cd agent
uv sync
uv run pytest
```

Integration tests under `tests/integration/auth/` boot a Keycloak container
via [testcontainers](https://testcontainers-python.readthedocs.io/), which
needs Docker or a Docker-compatible runtime running.

If you're using Podman, point testcontainers at the Podman socket and disable
Ryuk (Ryuk's privileges aren't available on the Podman machine):

```bash
DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')" \
    TESTCONTAINERS_RYUK_DISABLED=true \
    uv run pytest
```
