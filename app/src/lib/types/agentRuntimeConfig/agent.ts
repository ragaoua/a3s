import z from 'zod';
import { subagentsSchema } from './subagent';

export const agentSchema = z.object({
	name: z.string().min(1),
	description: z.string().min(1),
	instructions: z.string().min(1),
	subagents: subagentsSchema.optional()
});
