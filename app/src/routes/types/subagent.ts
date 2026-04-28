import type { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';

export interface Subagent {
	url: string;
	type: SubagentType;
	authMode: SubagentAuthMode;
	clientId: string;
	clientSecret: string;
	tokenEndpoint: string;
	authMethod: SubagentOauth2AuthMethod;
}

export function newSubagent(): Subagent {
	return {
		url: '',
		type: 'peer',
		authMode: 'none',
		clientId: '',
		clientSecret: '',
		tokenEndpoint: '',
		authMethod: 'client_secret_post'
	};
}

export const SUBAGENT_TYPE_OPTIONS = ['peer', 'delegate'] as const;

export type SubagentType = (typeof SUBAGENT_TYPE_OPTIONS)[number];

export const SUBAGENT_TYPE_LABELS: Record<SubagentType, string> = {
	peer: 'Peer',
	delegate: 'Delegate'
};

export const SUBAGENT_AUTH_MODE_OPTIONS = [
	'none',
	'oauth_client_credentials',
	'oauth_token_forward',
	'oauth_token_exchange'
] as const;

export type SubagentAuthMode = (typeof SUBAGENT_AUTH_MODE_OPTIONS)[number];

export const SUBAGENT_AUTH_MODE_LABELS: Record<SubagentAuthMode, string> = {
	none: 'None',
	oauth_client_credentials: 'OAuth2 Client Credentials',
	oauth_token_forward: 'OAuth2 Token Forward',
	oauth_token_exchange: 'OAuth2 Token Exchange'
};

export type SubagentOauth2AuthMethod = (typeof OAUTH2_AUTH_METHOD_OPTIONS)[number];

export const SUBAGENT_OAUTH2_AUTH_METHOD_LABELS: Record<SubagentOauth2AuthMethod, string> = {
	client_secret_post: 'POST',
	client_secret_basic: 'Basic'
};
