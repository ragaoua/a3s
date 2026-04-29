import z from 'zod';

export const skillFormSchema = z.object({
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
