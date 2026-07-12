# Contributing

## Running tests

```bash
cd agent
uv sync
uv run pytest
```

### Integration tests

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

### End-to-end tests

A manual end-to-end suite under `tests/e2e/` drives the engine through its real
`a3s-agent` entrypoint against a real LLM under OAuth2 inbound auth. The suite
is gated behind the `e2e` pytest marker so it's excluded from the default
`pytest` run, and behind three env vars that point at the LLM endpoint. Run it
with `-m e2e` after exporting them:

```bash
A3S_LLM_API_URL=http://localhost:11434/v1 \
    A3S_LLM_API_KEY=ollama \
    A3S_LLM_MODEL="qwen2.5:7b" \
    uv run pytest -m e2e
```

**Note**: `A3S_LLM_API_URL` is used as-is by the host-side test. For the
containerised test, the suite rewrites `localhost`/`127.0.0.1` in that URL to
`host.docker.internal` so the agent container can reach a host-side LLM through
the docker host-gateway alias. Remote provider URLs pass through unchanged.

E2E tests assert only that some non-empty text comes back within the timeout,
not on response content; they exist to catch breakage in the engine glue
(config loading, env-var substitution, OAuth2 middleware, CLI shutdown path)
that no other test layer exercises. Without the env vars set, every test in
the suite skips.
