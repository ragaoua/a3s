# TODO

Non-exhaustive list of features and enablers to implement; subject to change.

## Agent

- client-to-agent auth:
  - Agent card:
    - Extended authenticated agent card
    - Opt-in to protect agent card by auth
  - API Key:
    - Support multiple keys
    - Support key management: generation, rotation, revocation
      - The app would stop displaying the API Key upon deployment
  - OAuth2:
    - Maybe support setting multiple audiences ("one-of") instead of just the one ?
    - Implement token validation policies (and/or):
      - Signature check
        - Configure the alg allowlist ?
      - RFC 9068 (stricter validation)
      - Token introspection
      - Custom policy (validate custom claims values...)
    - Cache JWKS
    - Token validation errors aren't properly handled
  - OIDC:
  - mTLS:
- agent-to-MCP auth:
  - Configure auth per MCP:
    - No auth
    - Oauth2:
      - Forward agent token
      - client credentials flow (allow different issuer ?)
      - Token exchange (same issuer or different one that supports ?)
    - API Key ?
- Core features:
  - manage agents list
    - edit
    - delete
  - skills / subagents
  - Handle MCP elicitations
  - AG-UI support ?
  - Add builtin code execution tool (with opt-in/out configuration)
  - Persist session/memory/artifacts, instead of using inMemory, ephemeral services
- Technical enablers:
  - Improve error handling:
    - Errors related to the agent failing to access MCP Servers (401, 403...)
    - Errors related to the LLM API (litellm error...)
  - Test deploying to GKE/EKS
  - monkeypatch the llm call. Right now, test_no_auth.py::test_agent_is_reachable_in_no_auth_mode
    passes but the agent actually throws an error since LLM_API_URI is fake
  - Test:
    - Write better/more integration tests
    - Unit tests
    - e2e tests

## App

- Auth:
- Core features
  - After an agent has been deployed, should the platform configure (or provide
    a way to configure) a clusterIP/nodePort/loadbalancer/ingress service for external
    access to the agent ?
  - Run a deployment for agents, not a simple pod
  - Clean up per-agent ConfigMaps and Secrets when agent pods are deleted
- Technical enablers:
  - Test:
    - Unit tests
    - integration tests
    - e2e tests

  - Deployments currently create standalone pods directly (no built-in
    Service/Ingress/lifecycle orchestration). It is left to the Kubernetes
    admin to set up according to the use cases and internal policies
  - Right now, the app only supports deploying and listing agents. More
    management features will be added
