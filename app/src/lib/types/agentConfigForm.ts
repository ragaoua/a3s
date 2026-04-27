import z from 'zod';
import { OAUTH2_AUTH_METHOD_OPTIONS } from './agentRuntimeConfig/outboundAuth';

const mcpServerFormBaseSchema = z.object({ url: z.url() });

const mcpServerOAuthClientAuthSchema = mcpServerFormBaseSchema.extend({
	clientId: z.string().min(1),
	clientSecret: z.string().min(1),
	authMethod: z.enum(OAUTH2_AUTH_METHOD_OPTIONS)
});

const mcpServerFormSchema = z.discriminatedUnion('authMode', [
	mcpServerFormBaseSchema.extend({
		authMode: z.literal('none')
	}),
	mcpServerFormBaseSchema.extend({
		authMode: z.literal('oauth_token_forward')
	}),
	mcpServerOAuthClientAuthSchema.extend({
		authMode: z.literal('oauth_client_credentials'),
		tokenEndpoint: z.url()
	}),
	mcpServerOAuthClientAuthSchema.extend({
		authMode: z.literal('oauth_token_exchange'),
		tokenEndpoint: z.preprocess((v) => (v === '' ? undefined : v), z.url().optional())
	})
]);

const baseAgentConfigFormSchema = z.object({
	name: z.string().min(1),
	description: z.string().min(1),
	instructions: z.string().min(1),
	model: z.string().min(1),
	apiUrl: z.url(),
	apiKey: z.string().min(1),
	mcpServers: z.array(mcpServerFormSchema)
});

export const agentConfigFormSchema = z
	.discriminatedUnion('authMode', [
		baseAgentConfigFormSchema.extend({
			authMode: z.literal('none')
		}),
		baseAgentConfigFormSchema.extend({
			authMode: z.literal('apiKey')
		}),
		baseAgentConfigFormSchema.extend({
			authMode: z.literal('oauth2'),
			oauth2IssuerUrl: z.url()
		})
	])
	.superRefine((data, ctx) => {
		if (data.authMode === 'oauth2') return;

		data.mcpServers.forEach((server, index) => {
			if (server.authMode === 'oauth_token_forward' || server.authMode === 'oauth_token_exchange') {
				ctx.addIssue({
					code: 'custom',
					path: ['mcpServers', index, 'authMode'],
					message: `MCP server auth mode "${server.authMode}" requires the agent's auth mode to be oauth2.`
				});
			}
		});
	});

export type AgentConfigForm = z.infer<typeof agentConfigFormSchema>;
