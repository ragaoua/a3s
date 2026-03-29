# a3s

a3s stands for Agent as a Service. This project is comprised of 2 components:

1. The [agent](agent/) engine, which provides a flexible interface for running
   custom A2A agents, configurable with authentication and MCP integration.
2. The [platform](app): a web app to configure, manage and deploy agents on
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
cp config/agent.example.yaml config/agent.yaml # Edit to set the configuration
A3S_LLM_API_KEY="your-llm-api-key" uv run a3s-agent
```

Alternatively, build the container image and run it:

```bash
docker build -t a3s-agent ./agent
docker run \
    --interactive \
    --tty \
    --rm \
    -p 8000:8000 \
    -v "$(pwd)/agent/config/agent.yaml:/app/config/agent.yaml:ro" \
    -e A3S_LLM_API_KEY="your-llm-api-key" \
    a3s-agent
```

The agent is configured from a YAML file. By default, it reads
`config/agent.yaml` relative to the current working directory. Set
`A3S_CONFIG_FILE` to use a different config file path.

An example config lives at
[agent/config/agent.example.yaml](agent/config/agent.example.yaml) and the JSON
schema lives at
[agent/schemas/agent.config.schema.json](agent/schemas/agent.config.schema.json).

Variable substitution is supported in config values using the `${ENV_VAR}`
format. If the environment variable is missing, configuration validation fails.
This is useful for secrets such as API keys.

**Note**: by design, variable substitution only applies for values that fully
match `${ENV_VAR}`. So `agent.name: ${AGENT_NAME}` works (if `AGENT_NAME` is
set), but not `agent.name: prefix_${AGENT_NAME}`. The latter will be left
unchanged.

### Basic Configuration

Basic configuration settings are:

- `agent.name` (**required**)
- `agent.description` (**required**)
- `agent.instructions` (**required**)
- `server.listen_address`: defaults to `127.0.0.1`
- `server.listen_port`: defaults to `8000`
- `logging.level`: defaults to `INFO`. Possible levels are:
  - "ERROR"
  - "WARNING"
  - "INFO"
  - "DEBUG"
- `logging.format`: `json` or `plain`. Defaults to `plain`

### LLM Support

The engine supports any OpenAI-compatible API for connecting to an LLM.
Configure these fields:

- `llm.api_url` (**required**)
- `llm.api_key` (**required**): use of environment variable substitution is highly
  recommended;
- `llm.model` (**required**)

### Authorization

The agent supports 3 authorization modes configured through the **required**
`auth` field:

- `auth: none`: disables auth. Not recommended in prod environments
- `auth.mode: api_key`: enables auth through API Key
  - This **requires** that `auth.api_key` be set to any arbitrary string. Use
    of environment variable substitution is highly recommended;
- `auth.mode: oauth2`: enables oauth2 authorization
  - This **requires** that `auth.issuer_url` be set to the authorization
    server's endpoint
  - `auth.jwks_url` (optionnal) verrides the issuer's JWKS endpoint. If unset,
    JWKS endpoint is discovered
  - `auth.audience` (optionnal) defines the access token audience (`aud` claim)
    to validate. If unset, no audience validation is enforced.

**Note**: the agent card endpoint (`/.well-known/agent-card.json`) is publicly
accessible, even when auth is enabled.

#### OAuth2

If OAuth2 mode is enabled, the agent will look for a bearer token in the
`Authorization` HTTP header upon receiving a request. It will then fetch the
authorization server's JWKS to validate the token and grant (or deny) access.

For more information about how tokens are validated, check out
[agent/docs/oauth-token-validation.md](agent/docs/oauth-token-validation.md)

#### API Key

If API Key auth is configured, the agent will look for an `API-Key` HTTP header
for every request, and check its value against the configured API key.

### MCP configuration

Define the MCP servers an agent has access to with `mcp_servers` as a YAML list
of URLs.

When using API key for auth, or when auth is disabled, MCP servers will only
be accessible to the agent if they don't require authorization. Otherwise, the
agent will fail upon receiving a 401 from the MCP servers when trying to
access.

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

- **Remote cluster deployment**: deploys to a remote Kubernetes cluster.
- **In-cluster deployment**: if the app/platform itself is running inside of a
  Kubernetes cluster, it can be configured to deploy to that same cluster,
  using the credentials of the service account used by the app's pod.

In any case, a service account must be configured with proper permissions in
the namespace dedicated to running agents ; it must be able to create and list
pods as well as create secrets.

Use `K8S_AGENTS_NAMESPACE` to configure the namespace in which the agent pods
will be deployed.

Use `K8S_DEPLOY_MODE` to select the deployment mode:

- `inCluster` for in-cluster deployment. In that case, it is expected that the
  pod running the platform uses the service account mentioned above.
  If `K8S_AGENTS_NAMESPACE` is not set, the platform will try and fetch the
  service account's namespace and use it
- `remote`: in addition to `K8S_AGENTS_NAMESPACE`, set:
  - `K8S_CLUSTER_NAME`
  - `K8S_SERVER_URL`: the URL to the Kubernetes cluster
  - `K8S_SERVICE_ACCOUNT`: the service account mentioned earlier
  - `K8S_SERVICE_ACCOUNT_TOKEN`: a valid token for the service account
  - `K8S_SERVICE_ACCOUNT_NAMESPACE`: the namespace in which the service account
    lives
  - `K8S_CA_DATA`: base64-encoded certificate of the certificate authority
    that signed the Kubernetes API server’s certificate.
- `auto` (default): automatically checks the runtime environment to determine
  if it is running inside of a Kubernetes cluster, in which case the
  `inCluster` mode will be enabled. Otherwise, `remote` mode will be set.

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
