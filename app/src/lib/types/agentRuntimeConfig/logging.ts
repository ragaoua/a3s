import z from 'zod';

export const loggingSchema = z.object({
	level: z.enum(['INFO', 'DEBUG', 'WARNING', 'ERROR']),
	format: z.enum(['plain', 'json'])
});
