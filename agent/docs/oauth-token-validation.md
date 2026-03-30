This document describes access token validation behavior in the a3s agent when
OAuth2 mode is enabled.

Token signature validation:

- Token signature verification is done against JWKS configured under
  `auth.policies.jwks`.
- With `auth.policies.jwks.discovered: true`, the JWKS endpoint is discovered
  from the authorization server metadata. With `auth.policies.jwks.discovered:
false`, the agent uses `auth.policies.jwks.url` to fetch the JWKS.
- JWKS are fetched for each request (not fetched at server startup, no caching
  implemented).
- When JWKS discovery is used, the discovered metadata `issuer` must match the
  configured `auth.issuer_url` value.

RFC 9068 validation:

- With `auth.policies.rfc9068.enabled: true`, tokens are validated as [RFC 9068
  JWT access tokens](https://datatracker.ietf.org/doc/rfc9068/). This includes
  RFC 9068 claim validation, `typ` validation, issuer validation against
  `auth.issuer_url`, and audience validation against
  `auth.policies.rfc9068.resource_server`.

Custom claim validation:

- `auth.policies.claims` adds extra claim validation rules on top of the active
  policy set.
- `auth.policies.claims` currently supports exact string matching only.
- If `auth.policies.claims` defines a claim that is already validated by the
  RFC 9068 policy, the configured claim rule overrides the built-in RFC 9068
  validation for that claim.
- To keep the default RFC 9068 behavior for required claims such as `iss`,
  `aud`, `sub`, `exp`, `client_id`, `iat`, or `jti`, do not redefine them in
  `auth.policies.claims`.

Example:

```yaml
auth:
  mode: oauth2
  issuer_url: https://auth.example.com
  policies:
    jwks:
      discovered: true
    rfc9068:
      enabled: true
      resource_server: api://agent
    claims:
      scope: read write
      # If set, this overrides the RFC 9068 audience validation.
      # aud: api://legacy-agent
```
