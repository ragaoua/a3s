import z from 'zod';
import { OAUTH2_AUTH_METHOD_OPTIONS } from './agentRuntimeConfig/outboundAuth';

const outboundOAuthClientAuthFields = {
	clientId: z.string().min(1),
	clientSecret: z.string().min(1),
	authMethod: z.enum(OAUTH2_AUTH_METHOD_OPTIONS)
};

function outboundAuthArms<TShape extends z.ZodRawShape>(base: z.ZodObject<TShape>) {
	const oauthClient = base.extend(outboundOAuthClientAuthFields);
	return [
		base.extend({ authMode: z.literal('none') }),
		base.extend({ authMode: z.literal('oauth_token_forward') }),
		oauthClient.extend({
			authMode: z.literal('oauth_client_credentials'),
			tokenEndpoint: z.url()
		}),
		oauthClient.extend({
			authMode: z.literal('oauth_token_exchange'),
			tokenEndpoint: z.preprocess((v) => (v === '' ? undefined : v), z.url().optional())
		})
	] as const;
}

function addOauth2OnlyAuthModeIssues(
	ctx: z.RefinementCtx,
	items: ReadonlyArray<{ authMode: string }>,
	pathPrefix: string,
	entityLabel: string
) {
	items.forEach((item, index) => {
		if (item.authMode === 'oauth_token_forward' || item.authMode === 'oauth_token_exchange') {
			ctx.addIssue({
				code: 'custom',
				path: [pathPrefix, index, 'authMode'],
				message: `${entityLabel} auth mode "${item.authMode}" requires the agent's auth mode to be oauth2.`
			});
		}
	});
}

const mcpServerFormBaseSchema = z.object({ url: z.url() });

const mcpServerFormSchema = z.discriminatedUnion(
	'authMode',
	outboundAuthArms(mcpServerFormBaseSchema)
);

const subagentFormBaseSchema = z.object({
	name: z
		.string()
		.min(1)
		.max(64)
		.regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, {
			message:
				'Subagent name must be lowercase letters, numbers, and hyphens only, and must not start or end with a hyphen.'
		}),
	url: z.url(),
	type: z.enum(['peer', 'delegate'])
});

const subagentFormSchema = z.discriminatedUnion('authMode', [
	...outboundAuthArms(subagentFormBaseSchema),
	subagentFormBaseSchema.extend({
		authMode: z.literal('apikey'),
		apiKey: z.string().min(1)
	})
]);

const skillFormSchema = z.object({
	name: z
		.string()
		.min(1)
		.max(64)
		.regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, {
			message:
				'Skill name must be lowercase letters, numbers, and hyphens only, and must not start or end with a hyphen.'
		}),
	description: z.string().min(1).max(1024),
	content: z.string().min(1)
});

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
	// NOTE: this will be removed when the agent supports oauth_token_exchange
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
