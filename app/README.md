Install dependencies:

```bash
bun ci
```

Run the app:

```bash
bun run dev --open

# With podman
DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')" bun run dev --open
```

Build the image:

```bash
podman build -t a3s-app .
```
