import z from 'zod';
import { subagentSchema } from './subagent';

export const agentSchema = z.object({
	name: z.string().min(1),
	description: z.string().min(1),
	instructions: z.string().min(1),
	subagents: z.record(z.string().min(1), subagentSchema).optional()
});
