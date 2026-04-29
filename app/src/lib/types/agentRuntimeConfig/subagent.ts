import z from 'zod';
import {
	oauthClientCredentialsAuthSchema,
	oauthDiscoveredTokenExchangeAuthSchema,
	oauthStaticTokenExchangeAuthSchema,
	oauthTokenForwardAuthSchema,
	outboundApiKeyAuthSchema
} from './outboundAuth';

export const subagentSchema = z.object({
	url: z.url(),
	type: z.enum(['delegate', 'peer']),
	auth: z.union([
		z.literal('none'),
		oauthTokenForwardAuthSchema,
		oauthClientCredentialsAuthSchema,
		oauthDiscoveredTokenExchangeAuthSchema,
		oauthStaticTokenExchangeAuthSchema,
		outboundApiKeyAuthSchema
	])
});
