import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import z from "zod";

export const getServer = () => {
  const server = new McpServer(
    {
      name: "demo-mcp-server",
      version: "1.0.0",
    },
    {
      capabilities: {
        tools: {},
      },
    },
  );

  server.registerTool(
    "write_file",
    {
      title: "Write to a file",
      inputSchema: z.object({ name: z.string(), content: z.string() }),
    },
    async ({ name, content }) => {
      void content;
      return {
        content: [
          {
            type: "text",
            text: `File ${name} written`,
          },
        ],
      };
    },
  );

  return server;
};
