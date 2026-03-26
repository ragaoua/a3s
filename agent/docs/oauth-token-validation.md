This document provides information about token validation for the a3s agent
engine when enabling OAuth2 mode. This doc will be updated as new features /
changes are implemented.

Key points:

- Signature verification is done against JWKS (either configured URL via
  `OAUTH2_JWKS_URL` or discovered).
- JWKS are fetched for each request (No caching implemented, not fetched at
  server startup).
- If JWKS is discovered, metadata issuer is validated to match configured
  issuer
- An `iss` claim is required in the token's payload and validated against the
  value of the `OAUTH2_ISSUER_URL` environment variable.
- If `OAUTH2_AUDIENCE` is set, an `aud` claim is required and validated against
  the value of the environment variable. If the `aud` value is an array, is it
  considered valid if it contains the environment variable's configured value.
- If the token has an `exp`, `nbf` or `iat` claim, those are validated against
  the current date time (which should come before `exp`, and after `nbf` and
  `iat`).
