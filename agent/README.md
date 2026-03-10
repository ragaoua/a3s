Install the environment:

```bash
uv sync
```

Run the adk web console for testing:

```bash
export LLM_API_URI=
export LLM_API_KEY=
export AGENT_API_KEY=
export OAUTH2_ISSUER_URL= # e.g. https://keycloak.example.com/realms/my-realm
export OAUTH2_JWKS_URL= # optional override, otherwise discovered from <issuer>/.well-known/oauth-authorization-server
export MODEL=
export AGENT_NAME=
export AGENT_DESCRIPTION=
export AGENT_INSTRUCTIONS=
export LISTEN_PORT=
export MCP_SERVERS= # comma separated list of mcp endpoints (/!\ prefixed with "https://"), can be empty
uv run adk web
```

Expose the a2a agent:

```bash
export LLM_API_URI=
export LLM_API_KEY=
export AGENT_API_KEY=
export OAUTH2_ISSUER_URL= # e.g. https://keycloak.example.com/realms/my-realm
export OAUTH2_JWKS_URL= # optional override, otherwise discovered from <issuer>/.well-known/oauth-authorization-server
export MODEL=
export AGENT_NAME=
export AGENT_DESCRIPTION=
export AGENT_INSTRUCTIONS=
export LISTEN_PORT=
export MCP_SERVERS= # comma separated list of mcp endpoints (/!\ prefixed with "https://"), can be empty
uv run uvicorn agent:a2a_app --host localhost --port "$LISTEN_PORT"
```

Test the A2A agent:

```bash
export PORT="$LISTEN_PORT"
export AGENT_ACCESS_TOKEN=
uv run test_a2a.py # PORT=8000 is the default
```

Build and run the image:

```bash
podman build -t agent .
podman run \
    --interactive \
    --tty \
    --rm \
    --name aaas \
    -e MODEL= \
    -e AGENT_INSTRUCTIONS= \
    -e AGENT_DESCRIPTION= \
    -e AGENT_NAME= \
    -e LLM_API_URI= \
    -e LLM_API_KEY= \
    -e AGENT_API_KEY= \
    -e OAUTH2_ISSUER_URL= \
    -e OAUTH2_JWKS_URL= \
    -e MCP_SERVERS= \
    -e LISTEN_PORT="8001" \
    --publish 8001:8001 \
    localhost/agent
```

**Note**: for testing, use host.containers.internal instead of localhost
when connecting, from the container, to MCP servers hosted on the host
of the container.
