import z from 'zod';
import { OAUTH2_AUTH_METHOD_OPTIONS } from './outboundAuth';

const jwksPolicySchema = z.discriminatedUnion('discovered', [
	z.object({
		discovered: z.literal(true)
	}),
	z.object({
		discovered: z.literal(false),
		url: z.url()
	})
]);

const rfc9068PolicySchema = z.object({
	resource_server: z.string().min(1)
});

const jwtPolicySchema = z.object({
	jwks: jwksPolicySchema,
	rfc9068: rfc9068PolicySchema.optional(),
	claims: z.record(z.string().min(1), z.string().min(1)).optional()
});

const baseIntrospectionPolicySchema = z.object({
	client_id: z.string().min(1),
	client_secret: z.string().min(1),
	auth_method: z.enum(OAUTH2_AUTH_METHOD_OPTIONS).optional()
});

const introspectionPolicySchema = z.discriminatedUnion('discovered', [
	baseIntrospectionPolicySchema.extend({
		discovered: z.literal(true)
	}),
	baseIntrospectionPolicySchema.extend({
		discovered: z.literal(false),
		endpoint: z.url()
	})
]);

export const policiesSchema = z
	.object({
		jwt: jwtPolicySchema.optional(),
		introspection: introspectionPolicySchema.optional()
	})
	.refine((data) => data.jwt !== undefined || data.introspection !== undefined, {
		message: 'At least one of jwt or introspection policies must be configured.'
	});
export type OAuth2RuntimePolicies = z.infer<typeof policiesSchema>;

export const authSchema = z.union([
	z.literal('none'),
	z.object({
		mode: z.literal('api_key'),
		api_key: z.string().min(1)
	}),
	z.object({
		mode: z.literal('oauth2'),
		issuer_url: z.url(),
		policies: policiesSchema
	})
]);
