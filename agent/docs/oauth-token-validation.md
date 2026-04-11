This document describes access token validation behavior in the a3s agent when
OAuth2 mode is enabled.

Token signature validation:

- Token signature verification is done against JWKS configured under
  `auth.policies.jwt.jwks`. The `iss` claim is validated against
  `auth.issuer_url`.
- Registered JWT date claims such as `exp`, `nbf`, and `iat` are optional, but
  when present they are validated according to standard JWT semantics.
- With `auth.policies.jwt.jwks.discovered: true`, the JWKS endpoint is
  discovered from the authorization server metadata. With
  `auth.policies.jwt.jwks.discovered: false`, the agent uses
  `auth.policies.jwt.jwks.url` to fetch the JWKS.
- JWKS are fetched for each request (not fetched at server startup, no caching
  implemented).
- When JWKS discovery is used, the discovered metadata `issuer` must match the
  configured `auth.issuer_url` value.

Token introspection:

- `auth.policies.introspection` enables RFC 7662 token introspection.
- The introspection endpoint must return `{"active": true}`.
- Under `auth.policies.introspection`, `client_id` and `client_secret` are
  required. `auth_method` defaults to `client_secret_basic` and
  `client_secret_post` is also supported.
- With `auth.policies.introspection.discovered: true`, the introspection
  endpoint is discovered from the authorization server metadata. With
  `auth.policies.introspection.discovered: false`, the agent uses
  `auth.policies.introspection.endpoint`.
- The agent sends `token` and `token_type_hint=access_token` to the configured
  or discovered introspection endpoint.
- If the introspection endpoint reports `active: false`, the request is denied
  with `401 Unauthorized`. Introspection transport or response parsing failures
  return `503 Service Unavailable`.

RFC 9068 validation:

- When `auth.policies.jwt.rfc9068.resource_server` is set, tokens are validated as
  [RFC 9068 JWT access tokens](https://datatracker.ietf.org/doc/rfc9068/). This
  includes RFC 9068 claim validation, `typ` validation, issuer validation
  against `auth.issuer_url`, and audience validation against
  `auth.policies.jwt.rfc9068.resource_server`.

Custom claim validation:

- `auth.policies.jwt.claims` adds extra claim validation rules on top of the
  active policy set.
- `auth.policies.jwt.claims` currently supports exact string matching only.
- If `auth.policies.jwt.claims` defines a claim that is already validated by the
  RFC 9068 policy, the configured claim rule overrides the built-in RFC 9068
  validation for that claim.
- To keep the default RFC 9068 behavior for required claims such as `iss`,
  `aud`, `sub`, `exp`, `client_id`, `iat`, or `jti`, do not redefine them in
  `auth.policies.jwt.claims`.

Example:

```yaml
auth:
  mode: oauth2
  issuer_url: https://auth.example.com
  policies:
    jwt:
      jwks:
        discovered: true
      rfc9068:
        resource_server: api://agent
      claims:
        scope: read write
        # If set, this overrides the RFC 9068 audience validation.
        # aud: api://legacy-agent
    introspection:
      discovered: true
      # Or configure the endpoint directly instead:
      # discovered: false
      # endpoint: https://auth.example.com/oauth/introspect
      client_id: ${A3S_AGENT_INTROSPECTION_CLIENT_ID}
      client_secret: ${A3S_AGENT_INTROSPECTION_CLIENT_SECRET}
      auth_method: client_secret_basic
```
