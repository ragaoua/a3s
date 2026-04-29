import z from 'zod';
import {
	oauthClientCredentialsAuthSchema,
	oauthDiscoveredTokenExchangeAuthSchema,
	oauthStaticTokenExchangeAuthSchema,
	oauthTokenForwardAuthSchema,
	outboundApiKeyAuthSchema
} from './outboundAuth';

export const subagentsSchema = z.record(
	z.string().min(1),
	z.object({
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
	})
);

export type Subagents = z.infer<typeof subagentsSchema>;
