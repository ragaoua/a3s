import { newOutboundAuthConfig, type OutboundAuthConfig } from './outboundAuthConfig';

export interface McpServer extends OutboundAuthConfig {
	url: string;
}

export function newMcpServer(): McpServer {
	return {
		url: '',
		...newOutboundAuthConfig()
	};
}
