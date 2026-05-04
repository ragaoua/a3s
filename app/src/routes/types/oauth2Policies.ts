import { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';

export const OAUTH2_ENDPOINT_SOURCE_OPTIONS = ['discovered', 'static'] as const;

export type Oauth2EndpointSource = (typeof OAUTH2_ENDPOINT_SOURCE_OPTIONS)[number];

export const OAUTH2_ENDPOINT_SOURCE_LABELS: Record<Oauth2EndpointSource, string> = {
	discovered: 'Discovered from issuer',
	static: 'Static URL'
};

type Oauth2AuthMethod = (typeof OAUTH2_AUTH_METHOD_OPTIONS)[number];

export const OAUTH2_INTROSPECTION_AUTH_METHOD_LABELS: Record<Oauth2AuthMethod, string> = {
	client_secret_post: 'POST',
	client_secret_basic: 'Basic'
};

export interface Oauth2ClaimEntry {
	key: string;
	value: string;
}

export interface Oauth2JwtPolicy {
	jwksSource: Oauth2EndpointSource;
	jwksUrl: string;
	rfc9068Enabled: boolean;
	rfc9068ResourceServer: string;
	claims: Oauth2ClaimEntry[];
}

export function newOauth2JwtPolicy(): Oauth2JwtPolicy {
	return {
		jwksSource: 'discovered',
		jwksUrl: '',
		rfc9068Enabled: false,
		rfc9068ResourceServer: '',
		claims: []
	};
}

export interface Oauth2IntrospectionPolicy {
	endpointSource: Oauth2EndpointSource;
	endpoint: string;
	clientId: string;
	clientSecret: string;
	authMethod: Oauth2AuthMethod;
}

export function newOauth2IntrospectionPolicy(): Oauth2IntrospectionPolicy {
	return {
		endpointSource: 'discovered',
		endpoint: '',
		clientId: '',
		clientSecret: '',
		authMethod: 'client_secret_basic'
	};
}

export interface Oauth2PoliciesConfig {
	jwtEnabled: boolean;
	jwt: Oauth2JwtPolicy;
	introspectionEnabled: boolean;
	introspection: Oauth2IntrospectionPolicy;
}

export function newOauth2PoliciesConfig(): Oauth2PoliciesConfig {
	return {
		jwtEnabled: true,
		jwt: newOauth2JwtPolicy(),
		introspectionEnabled: false,
		introspection: newOauth2IntrospectionPolicy()
	};
}
