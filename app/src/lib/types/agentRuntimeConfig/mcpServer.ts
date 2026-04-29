import z from 'zod';
import { oauthAuthSchemas } from './outboundAuth';

export const mcpServerSchema = z.object({
	url: z.url(),
	auth: z.union([z.literal('none'), ...oauthAuthSchemas])
});
