import { CONFIG } from "./config";
import jwksRsa from "jwks-rsa";
import {
  decode,
  JsonWebTokenError,
  NotBeforeError,
  TokenExpiredError,
  verify,
  type JwtPayload,
} from "jsonwebtoken";
import { discoverAuthorizationServerMetadata } from "@modelcontextprotocol/sdk/client/auth.js";
import {
  InvalidTokenError,
  ServerError,
} from "@modelcontextprotocol/sdk/server/auth/errors.js";
import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import { requireBearerAuth } from "@modelcontextprotocol/sdk/server/auth/middleware/bearerAuth.js";

async function getJwksUri(): Promise<string> {
  if (CONFIG.auth.jwksUri !== undefined) {
    return CONFIG.auth.jwksUri;
  }

  try {
    const authServerMetadata = await discoverAuthorizationServerMetadata(
      CONFIG.auth.issuer,
    );
    if (authServerMetadata) {
      if (typeof authServerMetadata.jwks_uri === "string") {
        return authServerMetadata.jwks_uri;
      }
    }
  } catch (e) {}

  throw new ServerError("Authorization metadata discovery failed");
}

let jwksClientPromise: Promise<ReturnType<typeof jwksRsa>> | undefined;

async function getJwksClient(): Promise<ReturnType<typeof jwksRsa>> {
  if (!jwksClientPromise) {
    jwksClientPromise = (async () => {
      const jwksUri = await getJwksUri();
      return jwksRsa({
        jwksUri,
        cache: false,
        // cacheMaxAge: 10 * 60 * 1000,
        // rateLimit: true,
        // jwksRequestsPerMinute: 10,
        timeout: 5000,
      });
    })().catch((error: unknown) => {
      jwksClientPromise = undefined;
      throw error;
    });
  }

  return jwksClientPromise;
}

function parseScopes(scopeClaim: unknown): string[] {
  if (typeof scopeClaim === "string") {
    return scopeClaim
      .split(" ")
      .map((scope) => scope.trim())
      .filter((scope) => scope.length > 0);
  }

  if (Array.isArray(scopeClaim)) {
    return scopeClaim.filter(
      (scope): scope is string => typeof scope === "string" && scope.length > 0,
    );
  }

  return [];
}

function hasExpectedValue(
  value: string | string[] | undefined,
  expectedValue: string,
): boolean {
  if (typeof value === "string") {
    return value === expectedValue;
  }

  if (Array.isArray(value)) {
    return value.includes(expectedValue);
  }

  return false;
}

async function validateJwt(token: string): Promise<JwtPayload> {
  try {
    const decodedToken = decode(token, { complete: true });
    if (!decodedToken) {
      throw new InvalidTokenError("Malformed access token");
    }

    if (!decodedToken.header.kid) {
      throw new InvalidTokenError("Token header is missing kid");
    }

    if (
      !CONFIG.auth.allowedJwtAlgs.some(
        (allowed) => allowed == decodedToken.header.alg,
      )
    ) {
      throw new InvalidTokenError("Signing algorithm not allowed");
    }

    const jwksClient = await getJwksClient();
    const signingKey = await jwksClient.getSigningKey(decodedToken.header.kid);
    if (signingKey.alg !== decodedToken.header.alg) {
      throw new InvalidTokenError(
        "Token header alg doesn't match signing key's",
      );
    }

    const publicKey = signingKey.getPublicKey();
    const payload = verify(token, publicKey, {
      algorithms: CONFIG.auth.allowedJwtAlgs,
      issuer: CONFIG.auth.issuer,
    });

    if (typeof payload !== "object") {
      throw new InvalidTokenError("Invalid access token payload");
    }

    return payload;
  } catch (error) {
    if (error instanceof InvalidTokenError) {
      throw error;
    }

    if (error instanceof ServerError) {
      throw error;
    }

    if (error instanceof TokenExpiredError) {
      throw new InvalidTokenError("Token has expired");
    }

    if (error instanceof NotBeforeError) {
      throw new InvalidTokenError("Token is not active yet");
    }

    if (error instanceof JsonWebTokenError) {
      throw new InvalidTokenError("Token is invalid");
    }

    if (error instanceof Error && error.name === "SigningKeyNotFoundError") {
      throw new InvalidTokenError("Token signing key not found");
    }

    throw new ServerError("Failed to validate access token");
  }
}

async function verifyAccessToken(token: string): Promise<AuthInfo> {
  const payload = await validateJwt(token);

  const tokenClientId =
    typeof payload.azp === "string"
      ? payload.azp
      : typeof payload.client_id === "string"
        ? payload.client_id
        : undefined;

  const tokenIssuedForExpectedClient =
    tokenClientId === CONFIG.auth.clientId ||
    (!tokenClientId && hasExpectedValue(payload.aud, CONFIG.auth.clientId));

  if (!tokenIssuedForExpectedClient) {
    throw new InvalidTokenError("Token was not issued for this client");
  }

  if (payload.exp === undefined) {
    throw new InvalidTokenError("Token has no expiration time");
  }

  return {
    token,
    clientId: CONFIG.auth.clientId,
    scopes: parseScopes(payload.scope),
    expiresAt: payload.exp,
  };
}

export function getExpressAuthRouter(resourceMetadataUrl: string) {
  return requireBearerAuth({
    verifier: {
      verifyAccessToken,
    },
    // requiredScopes: [],
    resourceMetadataUrl,
  });
}
