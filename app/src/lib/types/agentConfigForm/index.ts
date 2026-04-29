import z from 'zod';
import { skillFormSchema } from './skill';
import { subagentFormSchema } from './subagent';
import { mcpServerFormSchema } from './mcpServer';
import { addOauth2OnlyAuthModeIssues } from './outboundAuth';

const baseAgentConfigFormSchema = z.object({
	name: z.string().min(1),
	description: z.string().min(1),
	instructions: z.string().min(1),
	model: z.string().min(1),
	apiUrl: z.url(),
	apiKey: z.string().min(1),
	mcpServers: z.array(mcpServerFormSchema),
	subagents: z.array(subagentFormSchema),
	skills: z.array(skillFormSchema)
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

		addOauth2OnlyAuthModeIssues(ctx, data.mcpServers, 'mcpServers', 'MCP server');
		addOauth2OnlyAuthModeIssues(ctx, data.subagents, 'subagents', 'Subagent');
	})
	// NOTE: this will be removed when the agent supports oauth_token_exchange.
	// See issue #11
	.superRefine((data, ctx) => {
		data.mcpServers.forEach((server, index) => {
			if (server.authMode === 'oauth_token_exchange') {
				ctx.addIssue({
					code: 'custom',
					path: ['mcpServers', index, 'authMode'],
					message: "mcp_servers[].auth.mode='oauth_token_exchange' is not implemented yet"
				});
			}
		});
	})
	.superRefine((data, ctx) => {
		const seen = new Set<string>();
		data.subagents.forEach((subagent, index) => {
			if (seen.has(subagent.name)) {
				ctx.addIssue({
					code: 'custom',
					path: ['subagents', index, 'name'],
					message: `Subagent name "${subagent.name}" is already used.`
				});
			}
			seen.add(subagent.name);
		});
	});

export type AgentConfigForm = z.infer<typeof agentConfigFormSchema>;
