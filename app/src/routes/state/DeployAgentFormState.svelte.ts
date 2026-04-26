export class DeployAgentFormState {
	agentName: string = $state('');
	description: string = $state('');
	instructions: string = $state('');

	model: string = $state('');
	apiUrl: string = $state('');
	apiKey: string = $state('');

	authMode: 'apiKey' | 'oauth2' | 'none' = $state('apiKey');
	oauth2IssuerUrl = $state('');

	mcpServers: string[] = $state([]);
	isPanelOpen = $state(false);
	mcpServerDraft = $state('');

	openPanel() {
		this.mcpServerDraft = '';
		this.isPanelOpen = true;
	}

	closePanel() {
		this.isPanelOpen = false;
		this.mcpServerDraft = '';
	}

	addMcpServer() {
		const mcpServer = this.mcpServerDraft.trim();

		if (mcpServer.length === 0) {
			return;
		}

		this.mcpServers = [...this.mcpServers, mcpServer];
		this.closePanel();
	}

	removeMcpServer(index: number) {
		this.mcpServers = this.mcpServers.filter((_, currentIndex) => currentIndex !== index);
	}
}
