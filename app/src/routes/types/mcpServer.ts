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
		authMethod: 'post'
	};
}

export const MCP_SERVER_AUTH_MODE_OPTIONS = [
	'none',
	'oauth2ClientCredentials',
	'oauth2TokenForward',
	'oauth2TokenExchange'
] as const;

export type McpServerAuthMode = (typeof MCP_SERVER_AUTH_MODE_OPTIONS)[number];

export const MCP_SERVER_AUTH_MODE_LABELS: Record<McpServerAuthMode, string> = {
	none: 'None',
	oauth2ClientCredentials: 'OAuth2 Client Credentials',
	oauth2TokenForward: 'OAuth2 Token Forward',
	oauth2TokenExchange: 'OAuth2 Token Exchange'
};

export const MCP_SERVER_OAUTH2_AUTH_METHOD_OPTIONS = ['post', 'basic'] as const;

export type McpServerOauth2AuthMethod = (typeof MCP_SERVER_OAUTH2_AUTH_METHOD_OPTIONS)[number];

export const MCP_SERVER_OAUTH2_AUTH_METHOD_LABELS: Record<McpServerOauth2AuthMethod, string> = {
	post: 'POST',
	basic: 'Basic'
};
