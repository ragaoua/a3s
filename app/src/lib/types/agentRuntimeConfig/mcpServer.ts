import z from 'zod';

export const mcpServerSchema = z.object({
	url: z.url(),
	auth: z.literal('none')
});
