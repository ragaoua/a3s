# Run Jaeger to collect traces

```bash
podman-compose up
```

Access the Jaeger UI through `http://localhost:16686` to see the traces.

Run an agent with telemetry enabled:

```bash
A3S_OTEL_ENABLED=true uv run a3s-agent
```
