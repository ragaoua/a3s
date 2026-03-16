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
    issuer: "http://localhost:8080/realms/myrealm",
    // jwksUri:
    //   "http://localhost:8080/realms/myrealm/protocol/openid-connect/certs",
    clientId: "chatbot-app",
    allowedJwtAlgs: ["RS256"],
  },
};
