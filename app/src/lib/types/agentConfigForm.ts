import z from 'zod';

const baseSchema = z.object({
	name: z.string().min(1),
	description: z.string().min(1),
	instructions: z.string().min(1),
	model: z.string().min(1),
	apiUrl: z.url(),
	apiKey: z.string().min(1),
	mcpServers: z.array(z.url())
});

export const agentConfigFormSchema = z.discriminatedUnion('authMode', [
	baseSchema.extend({
		authMode: z.literal('none')
	}),
	baseSchema.extend({
		authMode: z.literal('apiKey')
	}),
	baseSchema.extend({
		authMode: z.literal('oauth2'),
		oauth2IssuerUrl: z.url(),
		oauth2JwksUrl: z.url().optional(),
		oauth2Audience: z.string().optional()
	})
]);

export type AgentConfigForm = z.infer<typeof agentConfigFormSchema>;
