import { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';

export interface OutboundAuthConfig {
	authMode: OutboundAuthMode;
	clientId: string;
	clientSecret: string;
	tokenEndpoint: string;
	authMethod: OutboundOauth2AuthMethod;
	apiKey: string;
}

export function newOutboundAuthConfig(): OutboundAuthConfig {
	return {
		authMode: 'none',
		clientId: '',
		clientSecret: '',
		tokenEndpoint: '',
		authMethod: 'client_secret_post',
		apiKey: ''
	};
}

export const OUTBOUND_AUTH_MODE_OPTIONS = [
	'none',
	'oauth_client_credentials',
	'oauth_token_forward',
	'oauth_token_exchange',
	'apikey'
] as const;

export type OutboundAuthMode = (typeof OUTBOUND_AUTH_MODE_OPTIONS)[number];

export const OUTBOUND_AUTH_MODE_LABELS: Record<OutboundAuthMode, string> = {
	none: 'None',
	oauth_client_credentials: 'OAuth2 Client Credentials',
	oauth_token_forward: 'OAuth2 Token Forward',
	oauth_token_exchange: 'OAuth2 Token Exchange',
	apikey: 'API key'
};

type OutboundOauth2AuthMethod = (typeof OAUTH2_AUTH_METHOD_OPTIONS)[number];

export const OUTBOUND_OAUTH2_AUTH_METHOD_LABELS: Record<OutboundOauth2AuthMethod, string> = {
	client_secret_post: 'POST',
	client_secret_basic: 'Basic'
};
