import z from 'zod';
import { OAUTH2_AUTH_METHOD_OPTIONS } from '../agentRuntimeConfig/outboundAuth';

const outboundOAuthClientAuthFields = {
	clientId: z.string().min(1),
	clientSecret: z.string().min(1),
	authMethod: z.enum(OAUTH2_AUTH_METHOD_OPTIONS)
};

export function outboundAuthArms<TShape extends z.ZodRawShape>(base: z.ZodObject<TShape>) {
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

export function addOauth2OnlyAuthModeIssues(
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
