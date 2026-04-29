import z from 'zod';
import { outboundAuthArms } from './outboundAuth';

export const mcpServerFormSchema = z.discriminatedUnion(
	'authMode',
	outboundAuthArms(z.object({ url: z.url() }))
);
