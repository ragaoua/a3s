import z from 'zod';

export const agentRuntimeConfigSchema = z.object({
	llm: z.object({
		api_url: z.url(),
		api_key: z.string().min(1),
		model: z.string().min(1)
	}),
	agent: z.object({
		name: z.string().min(1),
		description: z.string().min(1),
		instructions: z.string().min(1)
	}),
	server: z.object({
		listen_address: z.union([z.ipv4(), z.literal('localhost')]),
		listen_port: z.number().min(1).max(65535)
	}),
	auth: z.union([
		z.literal('none'),
		z.object({
			mode: z.literal('api_key'),
			api_key: z.string().min(1)
		}),
		z.object({
			mode: z.literal('oauth2'),
			issuer_url: z.url(),
			jwks_url: z.url().optional(),
			audience: z.string().optional()
		})
	]),
	mcp_servers: z.array(z.url())
});

export type AgentRuntimeConfig = z.infer<typeof agentRuntimeConfigSchema>;
