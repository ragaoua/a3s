export class DeployAgentFormState {
	agentName: string = $state('');
	description: string = $state('');
	instructions: string = $state('');

	model: string = $state('');
	apiUrl: string = $state('');
	apiKey: string = $state('');

	authMode: 'apiKey' | 'oauth2' = $state('apiKey');
	oauth2IssuerUrl = $state('');
	oauth2JwksUrl = $state('');

	mcpServers: string[] = $state(['']);

	addMcpServer() {
		this.mcpServers = [...this.mcpServers, ''];
	}

	removeMcpServer(index: number) {
		if (this.mcpServers.length === 1) {
			this.mcpServers = [''];
			return;
		}

		this.mcpServers = this.mcpServers.filter((_, currentIndex) => currentIndex !== index);
	}
}
