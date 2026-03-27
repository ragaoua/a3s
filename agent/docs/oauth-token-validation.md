This document describes access token validation behavior in the a3s agent when
OAuth2 mode is enabled. It will be updated as new features and changes are
implemented.

Key points:

- Access tokens must comply with the [OAuth 2.0 JWT Access Token Profile RFC
  9068](https://datatracker.ietf.org/doc/rfc9068/). The token `iss` claim must
  match `OAUTH2_ISSUER_URL`.
- Token signature verification is done against JWKS, which is fetched using
  `OAUTH2_JWKS_URL` if set, or discovery from OAuth2 authorization server
  metadata.
- JWKS are fetched for each request (no caching implemented yet; not fetched at
  server startup).
- When JWKS discovery is used, the discovered metadata `issuer` must match the
  configured `OAUTH2_ISSUER_URL` value.
- If `OAUTH2_AUDIENCE` is set, audience/resource server validation is enforced
  against that value. Otherwise, the `aud` claim's validation is ignored.
