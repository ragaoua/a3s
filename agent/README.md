# a3s agent engine

The a3s agent engine is a configurable runtime that exposes a GenAI agent
through HTTP via Google's A2A protocol.

## Running an agent

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
    -v "$(pwd)/agent/config/skills:/app/config/skills:ro" \
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

## Basic Configuration

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

## Skills

The engine loads all skills found under the directory pointed by
`agent.skills_dir`. skills under this directory are expected to comply with the
[Agent Skills specification](https://agentskills.io/specification).

For the time being, agents do not have access to a code execution environment,
so scripts provided to an agent as part of a skill (under the skill's
`scripts` directory) cannot be used by the agent.

`agent.skills_dir` is optional. It defaults to `config/skills`. If the path is
missing, not a directory, or empty, the agent starts without loading any
skills.

## LLM Support

The engine supports any OpenAI-compatible API for connecting to an LLM.
Configure these fields:

- `llm.api_url` (**required**)
- `llm.api_key` (**required**): use of environment variable substitution is highly
  recommended
- `llm.model` (**required**)

## Authorization

The agent supports 3 authorization modes configured through the **required**
`auth` field:

- `auth: none`: disables auth. Not recommended in prod environments
- `auth.mode: api_key`: enables auth through API Key
- `auth.mode: oauth2`: enables oauth2 authorization

**Note**: the agent card endpoint (`/.well-known/agent-card.json`) is publicly
accessible, even when auth is enabled.

### API Key

If API Key auth is configured, the agent will look for an `API-Key` HTTP header
for every request, and check its value against the configured API key.

This mode **requires** that `auth.api_key` be set to any arbitrary string. Use of
environment variable substitution is highly recommended.

### OAuth2

If OAuth2 mode is enabled, the agent will look for a bearer token in the
`Authorization` HTTP header upon receiving a request. It will then validate the
token according to the configured policy set (see below).

See `config/agent.example.yaml` for the current config shape.

This mode **requires** that the following configuration parameters be set:

- `auth.issuer_url`: must point to the authorization server.
- `auth.policies`: configures the token validation policies. Policies are
  additive: all configured policies are evaluated and applied.

Under `auth.policies`, configurable policies are:

- token signature: use `jwt.jwks` to enable local JWT signature validation.
  Setting `jwt.jwks.discovered: true` discovers the JWKS endpoint from the
  authorization server metadata. `jwt.jwks.discovered: false` requires
  `jwt.jwks.url` and uses that to fetch the JWKS. The token `iss` claim is
  always validated against `auth.issuer_url`, and registered JWT date claims
  such as `exp`, `nbf`, and `iat` are validated when present.
- RFC 9068: `jwt.rfc9068.resource_server` enables RFC 9068 JWT access token
  validation, in which case the token's `aud` claim will be validated against
  this value. RFC 9068 validation requires `jwt.jwks` because it validates JWT
  structure and claims locally.
- Custom claim validation: `auth.policies.jwt.claims` adds extra claim
  validation rules. The current implementation only supports exact string
  matching. If `auth.policies.jwt.claims` contains a claim that is also
  validated by the RFC 9068 policy, the custom rule overrides the built-in RFC
  validation for that claim. Do not set RFC 9068 required claims in
  `auth.policies.jwt.claims` unless you intentionally want to override that
  validation.
- Token introspection: using `introspection` enables RFC 7662 token
  introspection. `introspection.discovered: true` discovers the
  `introspection_endpoint` from the authorization server metadata.
  `introspection.discovered: false` uses `introspection.endpoint` directly.
  `introspection.client_id` and `introspection.client_secret` are required.
  `introspection.auth_method` defaults to `client_secret_basic` and also
  supports `client_secret_post`.

At least one of `auth.policies.jwt` or `auth.policies.introspection` must be
configured. Both can be set simultaneously.

For more information about how tokens are validated, check out
[docs/oauth-token-validation.md](docs/oauth-token-validation.md)

## MCP configuration

Define the MCP servers an agent has access to with `mcp_servers` as a YAML list
of objects. Each entry must include a `url` and an `auth` property:

```yaml
mcp_servers:
  - url: http://mcp1.example.com/mcp
    auth: none

  - url: http://mcp2.example.com/mcp
    auth:
      mode: oauth_client_credentials
      token_endpoint: http://mcp2.example.com/mcp/token
      client_id: myclient
      client_secret: ${A3S_MCP2_CLIENT_SECRET}

  - url: http://mcp3.example.com/mcp
    auth:
      mode: oauth_token_forward
```

Supported MCP auth modes are:

- `auth: none`: no authorization is added to MCP requests. The MCP server must
  accept unauthenticated access.
- `auth.mode: oauth_client_credentials`: the agent obtains a token for that MCP
  server using the configured `token_endpoint`, `client_id`, and
  `client_secret`. `auth_method` defaults to `client_secret_basic` and also
  supports `client_secret_post`.
- `auth.mode: oauth_token_forward`: the agent forwards the inbound
  `Authorization` header to that MCP server. This requires root-level
  `auth.mode: oauth2`.
- `auth.mode: oauth_token_exchange`: the config shape is defined, and it also
  requires root-level `auth.mode: oauth2`, but this mode is not implemented yet
  and currently fails closed at runtime.
