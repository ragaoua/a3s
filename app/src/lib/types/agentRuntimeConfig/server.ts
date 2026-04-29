import z from 'zod';

export const serverSchema = z.object({
	listen_address: z.union([z.ipv4(), z.literal('localhost')]),
	listen_port: z.number().min(1).max(65535)
});
