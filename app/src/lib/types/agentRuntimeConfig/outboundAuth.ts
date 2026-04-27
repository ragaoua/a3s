import z from 'zod';

export const oauthTokenForwardAuthSchema = z.object({
	mode: z.literal('oauth_token_forward')
});

export const OAUTH2_AUTH_METHOD_OPTIONS = ['client_secret_post', 'client_secret_basic'] as const;

const oauthClientAuthSchema = z.object({
	client_id: z.string().min(1),
	client_secret: z.string().min(1),
	auth_method: z.enum(OAUTH2_AUTH_METHOD_OPTIONS)
});

export const oauthClientCredentialsAuthSchema = oauthClientAuthSchema.extend({
	mode: z.literal('oauth_client_credentials'),
	token_endpoint: z.url()
});

const oauthTokenExchangeAuthSchema = oauthClientAuthSchema.extend({
	mode: z.literal('oauth_token_exchange')
});

export const oauthDiscoveredTokenExchangeAuthSchema = oauthTokenExchangeAuthSchema.extend({
	discovered: z.literal(true)
});

export const oauthStaticTokenExchangeAuthSchema = oauthTokenExchangeAuthSchema.extend({
	discovered: z.literal(false),
	token_endpoint: z.url()
});
