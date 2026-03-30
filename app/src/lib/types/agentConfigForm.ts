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
	baseSchema
		.extend({
			authMode: z.literal('oauth2'),
			oauth2IssuerUrl: z.url(),
			oauth2JwksUrl: z.url().optional(),
			oauth2Rfc9068Enabled: z.boolean(),
			oauth2ResourceServer: z.string().min(1).optional()
		})
		.superRefine((data, ctx) => {
			if (data.oauth2Rfc9068Enabled && !data.oauth2ResourceServer) {
				ctx.addIssue({
					code: 'custom',
					path: ['oauth2ResourceServer'],
					message: 'Resource server is required when RFC 9068 validation is enabled'
				});
			}
		})
]);

export type AgentConfigForm = z.infer<typeof agentConfigFormSchema>;
