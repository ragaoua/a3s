# Test MCP

A minimal MCP server used for manual smoke testing. It exposes a single
`write_file` tool optionally behind OAuth 2.0 bearer-token auth.

## Launch

```sh
bun install
bun run start
```

Or via container:

```sh
podman build -t demo-mcp .
podman run --rm -p 3000:3000 demo-mcp
```

## Options

CLI flags:

| Flag          | Effect                     |
| ------------- | -------------------------- |
| `--no-auth`   | Disable OAuth bearer auth. |
| `--stateless` | Run in stateless mode.     |

Environment variables:

| Var               | Effect                                    | Default                                  |
| ----------------- | ----------------------------------------- | ---------------------------------------- |
| `HOST`            | Interface to bind.                        | `localhost`                              |
| `PORT`            | Port to listen on.                        | `3000`                                   |
| `ISSUER_URL`      | OAuth issuer expected in tokens.          | `http://localhost:8080/realms/a3s-realm` |
| `CLIENT_ID`       | Client ID tokens must be for.             | `a3s-test-client`                        |
| `ISSUER_JWKS_URL` | Static JWKS URI (skips issuer discovery). | _(unset — discovered from issuer)_       |

The remaining auth settings (allowed JWT algs) are hardcoded in
[`src/config.ts`](src/config.ts).
