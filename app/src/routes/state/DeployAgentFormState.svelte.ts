type PanelState<TKind extends 'mcpServer'> =
	| { kind: 'closed' }
	| { kind: TKind; mode: 'add' }
	| { kind: TKind; mode: 'edit'; index: number };

type MCPServerPanelState = PanelState<'mcpServer'>;
type OpenMcpServerPanelState = Exclude<MCPServerPanelState, { kind: 'closed' }>;

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
	mcpServerDraft = $state('');

	panelState: MCPServerPanelState = $state({ kind: 'closed' });

	panelTitle = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		return this.panelState.mode === 'add' ? 'Add MCP server' : 'Edit MCP server';
	});

	panelActionLabel = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		return this.panelState.mode === 'add' ? 'Add MCP server' : 'Update MCP server';
	});

	isPanelOpen = $derived.by(() => {
		return this.panelState.kind !== 'closed';
	});

	openPanel(panelState: OpenMcpServerPanelState) {
		this.panelState = panelState;
		this.mcpServerDraft =
			panelState.mode === 'edit' ? (this.mcpServers[panelState.index] ?? '') : '';
	}

	closePanel() {
		this.panelState = { kind: 'closed' };
		this.mcpServerDraft = '';
	}

	saveMcpServer() {
		const mcpServer = this.mcpServerDraft.trim();
		const panelState = this.panelState;

		if (mcpServer.length === 0 || panelState.kind !== 'mcpServer') {
			return;
		}

		if (panelState.mode === 'add') {
			this.mcpServers = [...this.mcpServers, mcpServer];
		} else {
			const editingIndex = panelState.index;
			this.mcpServers = this.mcpServers.map((currentMcpServer, index) =>
				index === editingIndex ? mcpServer : currentMcpServer
			);
		}

		this.closePanel();
	}

	removeMcpServer(index: number) {
		this.mcpServers = this.mcpServers.filter((_, currentIndex) => currentIndex !== index);
	}
}
