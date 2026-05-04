import z from 'zod';
import { OAUTH2_AUTH_METHOD_OPTIONS } from '../agentRuntimeConfig/outboundAuth';

export const OAUTH2_ENDPOINT_SOURCE_OPTIONS = ['discovered', 'static'] as const;

const oauth2EndpointSourceSchema = z.enum(OAUTH2_ENDPOINT_SOURCE_OPTIONS);

const oauth2ClaimSchema = z.object({
	key: z.string(),
	value: z.string()
});

const oauth2JwtPolicySchema = z.object({
	jwksSource: oauth2EndpointSourceSchema,
	jwksUrl: z.string(),
	rfc9068Enabled: z.boolean(),
	rfc9068ResourceServer: z.string(),
	claims: z.array(oauth2ClaimSchema)
});

const oauth2IntrospectionPolicySchema = z.object({
	endpointSource: oauth2EndpointSourceSchema,
	endpoint: z.string(),
	clientId: z.string(),
	clientSecret: z.string(),
	authMethod: z.enum(OAUTH2_AUTH_METHOD_OPTIONS)
});

export const oauth2PoliciesFormSchema = z
	.object({
		jwtEnabled: z.boolean(),
		jwt: oauth2JwtPolicySchema,
		introspectionEnabled: z.boolean(),
		introspection: oauth2IntrospectionPolicySchema
	})
	.superRefine((data, ctx) => {
		if (!data.jwtEnabled && !data.introspectionEnabled) {
			ctx.addIssue({
				code: 'custom',
				path: ['jwtEnabled'],
				message: 'At least one OAuth2 policy must be enabled.'
			});
		}

		if (data.jwtEnabled) {
			if (data.jwt.jwksSource === 'static' && !z.url().safeParse(data.jwt.jwksUrl).success) {
				ctx.addIssue({
					code: 'custom',
					path: ['jwt', 'jwksUrl'],
					message: 'JWKS URL must be a valid URL.'
				});
			}

			if (data.jwt.rfc9068Enabled && data.jwt.rfc9068ResourceServer.trim().length === 0) {
				ctx.addIssue({
					code: 'custom',
					path: ['jwt', 'rfc9068ResourceServer'],
					message: 'Resource server is required when RFC 9068 validation is enabled.'
				});
			}

			const seenKeys = new Set<string>();
			data.jwt.claims.forEach((claim, index) => {
				if (claim.key.trim().length === 0) {
					ctx.addIssue({
						code: 'custom',
						path: ['jwt', 'claims', index, 'key'],
						message: 'Claim key is required.'
					});
				}
				if (claim.value.trim().length === 0) {
					ctx.addIssue({
						code: 'custom',
						path: ['jwt', 'claims', index, 'value'],
						message: 'Claim value is required.'
					});
				}
				if (seenKeys.has(claim.key)) {
					ctx.addIssue({
						code: 'custom',
						path: ['jwt', 'claims', index, 'key'],
						message: `Claim "${claim.key}" is already defined.`
					});
				}
				seenKeys.add(claim.key);
			});
		}

		if (data.introspectionEnabled) {
			if (
				data.introspection.endpointSource === 'static' &&
				!z.url().safeParse(data.introspection.endpoint).success
			) {
				ctx.addIssue({
					code: 'custom',
					path: ['introspection', 'endpoint'],
					message: 'Introspection endpoint must be a valid URL.'
				});
			}

			if (data.introspection.clientId.trim().length === 0) {
				ctx.addIssue({
					code: 'custom',
					path: ['introspection', 'clientId'],
					message: 'Client ID is required.'
				});
			}

			if (data.introspection.clientSecret.length === 0) {
				ctx.addIssue({
					code: 'custom',
					path: ['introspection', 'clientSecret'],
					message: 'Client secret is required.'
				});
			}
		}
	});

export type Oauth2PoliciesForm = z.infer<typeof oauth2PoliciesFormSchema>;
