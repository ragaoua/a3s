import type { Request, Response } from "express";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { getExpressAuthRouter } from "./auth";
import { getServer } from "./server";
import { createRequestLogger } from "./logger";
import { CONFIG } from "./config";
import { getOAuthProtectedResourceMetadataUrl } from "@modelcontextprotocol/sdk/server/auth/router.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { randomUUID } from "node:crypto";

const authIsEnabled = !process.argv.includes("--no-auth");

const mcpServerUrl = new URL(`http://${CONFIG.host}:${CONFIG.port}`);
const mcpEndpointUrl = new URL("mcp", mcpServerUrl);

const app = createMcpExpressApp();

app.use(createRequestLogger());

const transports: Record<string, StreamableHTTPServerTransport> = {};

const mcpHandler = async (req: Request, res: Response) => {
  const sid = req.headers["mcp-session-id"] as string | undefined;

  let transport: StreamableHTTPServerTransport | undefined = sid
    ? transports[sid]
    : undefined;

  if (!transport && isInitializeRequest(req.body)) {
    const server = getServer();

    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (sessionId) => {
        transports[sessionId] = transport as StreamableHTTPServerTransport;
      },
    });

    await server.connect(transport);
  }

  if (!transport) {
    return res.status(400).json({
      jsonrpc: "2.0",
      error: { code: -32000, message: "Bad Request: invalid session" },
      id: null,
    });
  }

  try {
    await transport.handleRequest(req, res, req.body);
  } catch (err) {
    console.error("MCP error:", err);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null,
      });
    }
  }
};

const resourceMetadataUrl =
  getOAuthProtectedResourceMetadataUrl(mcpEndpointUrl);
if (authIsEnabled) {
  const authHandler = getExpressAuthRouter(resourceMetadataUrl);

  console.log("Authentication enabled - JWT validation required");
  app.post("/mcp", authHandler, mcpHandler);
  app.get("/mcp", authHandler, mcpHandler);
} else {
  console.log("⚠️  Authentication disabled - running in no-auth mode");
  app.post("/mcp", mcpHandler);
  app.get("/mcp", mcpHandler);
}

app.listen(CONFIG.port, CONFIG.host, () => {
  console.log(`🚀 MCP Server running on ${mcpServerUrl.origin}`);
  console.log(`📡 MCP endpoint available at ${mcpEndpointUrl}`);
  console.log(`🔐 OAuth metadata available at ${resourceMetadataUrl}`);
  console.log(
    `Auth mode: ${authIsEnabled ? "ENABLED" : "DISABLED (--no-auth)"}`,
  );
});

// Handle server shutdown
process.on("SIGINT", async () => {
  console.log("Shutting down server...");
  process.exit(0);
});
