import { type Algorithm } from "jsonwebtoken";

interface Config {
  host: string;
  port: number;
  auth: {
    issuer: string;
    jwksUri?: string; // if not set, discovered
    clientId: string;
    allowedJwtAlgs: Algorithm[];
  };
}

export const CONFIG: Config = {
  host: process.env.HOST || "localhost",
  port: Number(process.env.PORT) || 3000,
  auth: {
    issuer: process.env.ISSUER_URL || "http://localhost:8080/realms/a3s-realm",
    jwksUri: process.env.ISSUER_JWKS_URL ?? undefined,
    clientId: process.env.CLIENT_ID || "a3s-test-client",
    allowedJwtAlgs: ["RS256"],
  },
};
