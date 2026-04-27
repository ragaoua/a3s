import z from 'zod';
import { llmSchema } from './llm';
import { agentSchema } from './agent';
import { serverSchema } from './server';
import { authSchema } from './auth';
import { mcpServerSchema } from './mcpServer';
import { loggingSchema } from './logging';

export const agentRuntimeConfigSchema = z.object({
	llm: llmSchema,
	agent: agentSchema,
	server: serverSchema,
	auth: authSchema,
	mcp_servers: z.array(mcpServerSchema),
	logging: loggingSchema
});

export type AgentRuntimeConfig = z.infer<typeof agentRuntimeConfigSchema>;
