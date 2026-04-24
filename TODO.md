# TODO

Non-exhaustive list of features and enablers to implement; subject to change.

## Agent

- client-to-agent auth:
  - Agent card:
    - Extended authenticated agent card
    - Opt-in to protect agent card by auth
  - API Key:
  - OAuth2:
    - Add `private_key_jwt` as an `auth_method` for
      `auth.policies.introspection`
    - Token validation errors aren't properly handled
  - mTLS: ?
- agent-to-MCP auth:
  - Configure auth per MCP:
    - Add `private_key_jwt` as an `auth_method` for `mcp_servers[].auth`
    - API Key ?
- agent-to-agent auth:
  - Allow for configuring the header name which still should default to "API-Key"
- Core features:
  - Handle MCP elicitations
  - AG-UI support ?
  - Add builtin code execution tool (with opt-in/out configuration)
- Technical enablers:
  - Test deploying to GKE/EKS
  - monkeypatch the llm call. Right now, test_no_auth.py::test_agent_is_reachable_in_no_auth_mode
    passes but the agent actually throws an error since llm.api_url is fake

## App

- Auth:
- Core features
  - After an agent has been deployed, should the platform configure (or provide
    a way to configure) a clusterIP/nodePort/loadbalancer/ingress service for external
    access to the agent ?
  - Run a deployment for agents, not a simple pod
  - Clean up per-agent ConfigMaps and Secrets when agent pods are deleted
