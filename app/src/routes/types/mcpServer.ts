export interface McpServer {
	url: string;
	authMode: McpServerAuthMode;
}

export function newMcpServer(): McpServer {
	return {
		url: '',
		authMode: 'none'
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
