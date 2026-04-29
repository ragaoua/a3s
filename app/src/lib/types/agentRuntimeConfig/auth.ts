import z from 'zod';

const oauthJwksPolicySchema = z.discriminatedUnion('discovered', [
	z.object({
		discovered: z.literal(true)
	}),
	z.object({
		discovered: z.literal(false),
		url: z.url()
	})
]);

export const authSchema = z.union([
	z.literal('none'),
	z.object({
		mode: z.literal('api_key'),
		api_key: z.string().min(1)
	}),
	z.object({
		mode: z.literal('oauth2'),
		issuer_url: z.url(),
		policies: z.object({
			jwt: z.object({
				jwks: oauthJwksPolicySchema
			})
		})
	})
]);
