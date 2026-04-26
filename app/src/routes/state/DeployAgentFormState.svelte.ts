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
	editingMcpServerIndex: number | null = $state(null);

	openPanel(index?: number) {
		this.editingMcpServerIndex = typeof index === 'number' ? index : null;
		this.mcpServerDraft = typeof index === 'number' ? (this.mcpServers[index] ?? '') : '';
		this.isPanelOpen = true;
	}

	closePanel() {
		this.isPanelOpen = false;
		this.mcpServerDraft = '';
		this.editingMcpServerIndex = null;
	}

	saveMcpServer() {
		const mcpServer = this.mcpServerDraft.trim();

		if (mcpServer.length === 0) {
			return;
		}

		if (this.editingMcpServerIndex === null) {
			this.mcpServers = [...this.mcpServers, mcpServer];
		} else {
			this.mcpServers = this.mcpServers.map((currentMcpServer, index) =>
				index === this.editingMcpServerIndex ? mcpServer : currentMcpServer
			);
		}

		this.closePanel();
	}

	removeMcpServer(index: number) {
		this.mcpServers = this.mcpServers.filter((_, currentIndex) => currentIndex !== index);
	}
}
