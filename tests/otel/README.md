# Run open telemetry backend

## Run Jaeger

```bash
cd jaeger
podman-compose up
```

Access the Jaeger UI through `http://localhost:16686` to see the traces.

Run an agent with telemetry enabled:

```bash
# OTEL_EXPORTER_OTLP_ENDPOINT defaults to http://localhost:4318
A3S_OTEL_ENABLED=true uv run a3s-agent
```

## Run langfuse

```bash
cd langfuse
LANGFUSE_INIT_ORG_ID=my-org \
    LANGFUSE_INIT_ORG_NAME="My Org" \
    LANGFUSE_INIT_PROJECT_ID=my-project \
    LANGFUSE_INIT_PROJECT_NAME="My Project" \
    LANGFUSE_INIT_PROJECT_PUBLIC_KEY="lf_pk_1234567890" \
    LANGFUSE_INIT_PROJECT_SECRET_KEY="lf_sk_1234567890" \
    LANGFUSE_INIT_USER_NAME="John Doe" \
    LANGFUSE_INIT_USER_EMAIL='john@doe.com' \
    LANGFUSE_INIT_USER_PASSWORD='password$1' \
    podman-compose up -d
```

**Note**: The docker-compose file comes from the langfuse git repo :

```bash
wget https://raw.githubusercontent.com/langfuse/langfuse/refs/heads/main/docker-compose.yml
```

Access `localhost:3000` and register a new user.

Run the agent :

```bash
A3S_OTEL_ENABLED=true \
    OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:3000/api/public/otel" \
    OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n 'lf_pk_1234567890:lf_sk_1234567890' | base64)" \
    uv run a3s-agent
```
