import { newMcpServer, type McpServer } from '../types/mcpServer';

export type AgentAuthMode = 'apiKey' | 'oauth2' | 'none';

type PanelKinds = 'mcpServer';

type ClosedPanelState = { kind: 'closed' };
type OpenPanelState<TKind extends PanelKinds> =
	| { kind: TKind; mode: 'add' }
	| { kind: TKind; mode: 'edit'; index: number };

type McpServerPanelState = OpenPanelState<'mcpServer'>;

export class DeployAgentFormState {
	agentName: string = $state('');
	description: string = $state('');
	instructions: string = $state('');

	model: string = $state('');
	apiUrl: string = $state('');
	apiKey: string = $state('');

	authMode: AgentAuthMode = $state('apiKey');
	oauth2IssuerUrl = $state('');

	mcpServers: McpServer[] = $state([]);
	mcpServerDraft: McpServer = $state(newMcpServer());

	panelState: ClosedPanelState | OpenPanelState<PanelKinds> = $state({ kind: 'closed' });

	panelTitle = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		let title = this.panelState.mode === 'add' ? 'Add' : 'Edit';
		if (this.panelState.kind === 'mcpServer') {
			title += ' MCP server';
		}
		return title;
	});

	panelActionLabel = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		let title = this.panelState.mode === 'add' ? 'Add' : 'Update';
		if (this.panelState.kind === 'mcpServer') {
			title += ' MCP server';
		}
		return title;
	});

	openPanel<TKind extends PanelKinds>(panelState: OpenPanelState<TKind>) {
		this.panelState = panelState;

		if (panelState.kind === 'mcpServer') {
			this.mcpServerDraft =
				panelState.mode === 'edit'
					? { ...(this.mcpServers[panelState.index] ?? newMcpServer()) }
					: newMcpServer();
		}
	}

	closePanel() {
		this.panelState = { kind: 'closed' };
	}

	saveAndClosePanel() {
		if (this.panelState.kind === 'mcpServer') {
			this.saveMcpServer(this.panelState);
		}

		this.closePanel();
	}

	private saveMcpServer(panelState: McpServerPanelState) {
		const mcpServer = {
			...this.mcpServerDraft,
			url: this.mcpServerDraft.url.trim()
		};

		if (mcpServer.url.length === 0) {
			return;
		}

		if (panelState.mode === 'add') {
			this.mcpServers = [...this.mcpServers, mcpServer];
		} else {
			this.mcpServers = this.mcpServers.map((currentMcpServer, index) =>
				index === panelState.index ? mcpServer : currentMcpServer
			);
		}
	}

	removeMcpServer(index: number) {
		this.mcpServers = this.mcpServers.filter((_, currentIndex) => currentIndex !== index);
	}
}
