# a3s

a3s stands for Agent as a Service. This project is comprised of 2 components:

1. The [agent](agent/) engine, which provides a flexible interface for running
   custom A2A agents, configurable with authentication and MCP integration.
2. A [platform](app): a web app to configure, manage and deploy agents on
   Kubernetes.

While the platform relies entirely on the a3s agent engine, the latter can be
used as a standalone unit to deploy on any other platform than Kubernetes, or
as a building block for other use cases.

## The agent engine

The agent engine is a configurable runtime that exposes a GenAI agent through
HTTP via Google's A2A protocol.

### Running an agent

```bash
cd agent
uv sync
cp .env.example .env # Edit to set the configuration
uv run a3s-agent
```

Alternatively, build the container image and run it:

```bash
docker build -t a3s-agent ./agent
cp .env.example .env # Edit to set the configuration
docker run -it --env-file .env -p 8000:8000 a3s-agent
```

The agent's configuration is driven by environment variables. Those can be
set inside a `.env` file at the root of the `agent/` project.
The [.env.example](agent/.env.example) file lists all possible variables.

Exported variables override those set in `.env`.

### Basic configuration

- `AGENT_NAME`
- `AGENT_DESCRIPTION`
- `AGENT_INSTRUCTIONS`
- `LISTEN_ADDRESS`: defaults to "127.0.0.1"
- `LISTEN_PORT`: defaults to "8000"
- `LOG_LEVEL`: defaults to "INFO". Possible levels are:
  - "ERROR"
  - "WARNING"
  - "INFO"
  - "DEBUG"
- `LOG_FORMAT`: "json" or "plain". Defaults to "plain"

### LLM support

The engine supports any OpenAI-compatible API for connecting to an LLM. Provide
the `LLM_API_URI`, `LLM_API_KEY` and `MODEL` environment variables when running
the agent.

### Access control

The agent can be set to accept one of 2 authorization modes: OAuth2 or API Key.

Authentication can also be disabled by setting `NO_AUTH` to a _truthy_ value:
`1` or `true` (case-insensitive).

**Note**: the agent card endpoint (`/.well-known/agent-card.json`) is publicly
accessible, even when auth is enabled.

#### OAuth2

Setting `OAUTH2_ISSUER_URL` to an authorization server enables OAuth2 mode.
Optionally set:

- `OAUTH2_AUDIENCE` to validate the access token audience (`aud` claim). If
  unset, no audience validation will be enforced.
- `OAUTH2_JWKS_URL` to override the JWKS endpoint that is discovered otherwise.

Upon receiving a request, the agent will look for a bearer token in the
`Authorization` HTTP header. It will then fetch the authorization server's JWKS
to validate the token and grant (or deny) access.

For more information about how token validation is implemented, check out
[token-validation.md](agent/docs/token-validation.md)

#### API Key

Set `AGENT_API_KEY` to any arbitrary string value to enable API Key auth mode.

Upon receiving a request, the agent will look for an `API-Key` HTTP header,
and check its value against the configured API key.

### MCP configuration

Define the MCP servers an agent has access to with `MCP_SERVERS` as a
comma-separated list of URLs.

When using API key for auth, or when auth is disabled, MCP servers will only
be accessible to the agent if they don't require authorization.

In OAuth2 mode, the `Authorization` header used by the client is transferred to
the MCP servers. This allows agents to access MCP servers that require
authorized access, but it requires the agent and MCP servers to share the
same authorization server.

## The platform

The platform provides a UI where users define agent settings (model,
description, instructions, LLM endpoint, auth mode, MCP servers) and
trigger deployment to Kubernetes.

For each deployment request, the app creates a Kubernetes pod running the agent
engine container.

When selecting API Key auth mode, the platform generates an API Key and
displays it to the user.

### Running the platform

```bash
cd app
bun ci
bun run dev
```

### Kubernetes deployment modes

Regarding Kubernetes deployment of agents, the platform operates in 2 modes:

- **Remote cluster deployment**: the platform deploys to a remote Kubernetes
  cluster.
- **In-cluster deployment**: if the platform itself is running inside of a
  Kubernetes cluster, it can be configured to deploy to that same cluster,
  using the credentials of the service account used by the platform's pod.

Use `K8S_AGENTS_NAMESPACE` to configure the namespace in which the agent pods
will be deployed.

Use `K8S_DEPLOY_MODE` to select the deployment mode:

- `inCluster` for in-cluster deployment. In that case, it is expected that the
  pod running the platform uses a service account with proper "list" and
  "create" permissions for pods in the agents namespace.
  If `K8S_AGENTS_NAMESPACE` is not set, the platform will try and fetch the
  service account's namespace and use it.
- `remote`: in addition to `K8S_AGENTS_NAMESPACE`, set:
  - `K8S_CLUSTER_NAME`
  - `K8S_SERVER_URL`: the URL to the Kubernetes cluster
  - `K8S_SERVICE_ACCOUNT`: a service account that has proper permissions to
    list and create pods in the namespace dedicated to running agents
    (defined by `K8S_AGENTS_NAMESPACE`)
  - `K8S_SERVICE_ACCOUNT_TOKEN`: a valid token for the service account
  - `K8S_SERVICE_ACCOUNT_NAMESPACE`: the namespace in which the service account
    lives
  - `K8S_CA_DATA`: base64-encoded certificate of the certificate authority
    that signed the Kubernetes API server’s certificate.
- `auto` (default): automatically checks the runtime environment to determine
  if it is running inside of a Kubernetes cluster, in which case the
  `inCluster` mode will be enabled. Otherwise, `remote` mode will be set.

#### Required Kubernetes permissions

The service account used by the app's pod must be allowed to list and create
pods in the target namespace (same namespace or a different one, depending on
your RBAC setup).

## Current limitations and planned features

Deployments currently create standalone pods directly (no built-in
Service/Ingress/lifecycle orchestration). It is left to the Kubernetes admin to
set up according to the use cases and internal policies.

Right now, the platform only supports deploying and listing agents. More
management features will be added.

Check out [TODO.md](TODO.md) for more information about planned features and
future work.

## Dev environment setup: Git hooks

This repository includes a pre-commit hook in `.githooks/pre-commit`.

Enable it:

```bash
git config core.hooksPath .githooks
```
