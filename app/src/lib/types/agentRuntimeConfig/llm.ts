import z from 'zod';

export const llmSchema = z.object({
	api_url: z.url(),
	api_key: z.string().min(1),
	model: z.string().min(1)
});
