Transport security (URL schemes):

- In production, `auth.issuer_url` should use the `https` scheme. When the agent
  discovers authorization server metadata (any policy with `discovered: true`),
  it also requires the discovered `issuer`, `jwks_uri`, and
  `introspection_endpoint` to use `https`. A non-`https` URL fails validation and
  the request is rejected with `503 Service Unavailable`.
- For local development over plain HTTP, the `https` requirement is relaxed only
  for loopback hosts with an explicit port: `http://localhost:<port>` or
  `http://127.0.0.1:<port>`. The port is mandatory — `http://localhost` (no
  port) is rejected.
- Any other non-`https` host (a container or service name such as
  `http://keycloak:8080`, or a LAN IP) requires the `AUTHLIB_INSECURE_TRANSPORT`
  environment variable to be set (to any non-empty value) for validation to
  pass.
- `AUTHLIB_INSECURE_TRANSPORT` disables transport-security checks globally and is
  intended for local development only. Never set it in production.
