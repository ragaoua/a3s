import type { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';

export interface McpServer {
	url: string;
	authMode: McpServerAuthMode;
	clientId: string;
	clientSecret: string;
	tokenEndpoint: string;
	authMethod: McpServerOauth2AuthMethod;
}

export function newMcpServer(): McpServer {
	return {
		url: '',
		authMode: 'none',
		clientId: '',
		clientSecret: '',
		tokenEndpoint: '',
		authMethod: 'client_secret_post'
	};
}

export const MCP_SERVER_AUTH_MODE_OPTIONS = [
	'none',
	'oauth_client_credentials',
	'oauth_token_forward',
	'oauth_token_exchange'
] as const;

export type McpServerAuthMode = (typeof MCP_SERVER_AUTH_MODE_OPTIONS)[number];

export const MCP_SERVER_AUTH_MODE_LABELS: Record<McpServerAuthMode, string> = {
	none: 'None',
	oauth_client_credentials: 'OAuth2 Client Credentials',
	oauth_token_forward: 'OAuth2 Token Forward',
	oauth_token_exchange: 'OAuth2 Token Exchange'
};

export type McpServerOauth2AuthMethod = (typeof OAUTH2_AUTH_METHOD_OPTIONS)[number];

export const MCP_SERVER_OAUTH2_AUTH_METHOD_LABELS: Record<McpServerOauth2AuthMethod, string> = {
	client_secret_post: 'POST',
	client_secret_basic: 'Basic'
};
