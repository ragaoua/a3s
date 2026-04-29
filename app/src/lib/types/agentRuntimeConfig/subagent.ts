import z from 'zod';
import { oauthAuthSchemas, outboundApiKeyAuthSchema } from './outboundAuth';

export const subagentsSchema = z.record(
	z.string().min(1),
	z.object({
		url: z.url(),
		type: z.enum(['delegate', 'peer']),
		auth: z.union([z.literal('none'), ...oauthAuthSchemas, outboundApiKeyAuthSchema])
	})
);

export type Subagents = z.infer<typeof subagentsSchema>;
