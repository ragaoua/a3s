Install the environment:

```bash
uv sync
```

Run the adk web console for testing:

```bash
export API_URI=
export API_KEY=
export AGENT_NAME=
export AGENT_DESCRIPTION=
export AGENT_INSTRUCTIONS=
export LISTEN_PORT=
uv run adk web
```

Expose the a2a agent:

```bash
export API_URI=
export API_KEY=
export AGENT_NAME=
export AGENT_DESCRIPTION=
export AGENT_INSTRUCTIONS=
export LISTEN_PORT=
uv run uvicorn currency_agent.agent:a2a_app --host localhost --port 10000
```

Test the A2A agent:

```bash
uv run agent/test_a2a.py
```

Build and run the image:

```bash
podman build -t agent .
podman run \
    --interactive \
    --tty \
    --rm \
    --name aaas \
    -e AGENT_INSTRUCTIONS= \
    -e AGENT_DESCRIPTION= \
    -e AGENT_NAME= \
    -e API_URI= \
    -e API_KEY= \
    -e LISTEN_PORT="8001" \
    --publish 8001:8001 \
    localhost/agent
```
