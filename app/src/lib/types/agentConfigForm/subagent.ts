import z from 'zod';
import { outboundAuthArms } from './outboundAuth';

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

export const subagentFormSchema = z.discriminatedUnion('authMode', [
	...outboundAuthArms(subagentFormBaseSchema),
	subagentFormBaseSchema.extend({
		authMode: z.literal('apikey'),
		apiKey: z.string().min(1)
	})
]);
