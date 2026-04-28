import { newMcpServer, type McpServer } from '../types/mcpServer';
import { newSkill, type Skill } from '../types/skill';

export type AgentAuthMode = 'apiKey' | 'oauth2' | 'none';

type PanelKinds = 'mcpServer' | 'skill';

type ClosedPanelState = { kind: 'closed' };
type OpenPanelState<TKind extends PanelKinds> =
	| { kind: TKind; mode: 'add' }
	| { kind: TKind; mode: 'edit'; index: number };

type AnyOpenPanelState = TKindToOpenPanelState<PanelKinds>;
type TKindToOpenPanelState<TKind extends PanelKinds> = TKind extends PanelKinds
	? OpenPanelState<TKind>
	: never;

type McpServerPanelState = OpenPanelState<'mcpServer'>;
type SkillPanelState = OpenPanelState<'skill'>;

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

	skills: Skill[] = $state([]);
	skillDraft: Skill = $state(newSkill());

	panelState: ClosedPanelState | AnyOpenPanelState = $state({ kind: 'closed' });

	panelTitle = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		let title = this.panelState.mode === 'add' ? 'Add' : 'Edit';
		if (this.panelState.kind === 'mcpServer') {
			title += ' MCP server';
		} else if (this.panelState.kind === 'skill') {
			title += ' skill';
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
		} else if (this.panelState.kind === 'skill') {
			title += ' skill';
		}
		return title;
	});

	openPanel(panelState: AnyOpenPanelState) {
		this.panelState = panelState;

		if (panelState.kind === 'mcpServer') {
			this.mcpServerDraft =
				panelState.mode === 'edit'
					? { ...(this.mcpServers[panelState.index] ?? newMcpServer()) }
					: newMcpServer();
		} else if (panelState.kind === 'skill') {
			this.skillDraft =
				panelState.mode === 'edit'
					? { ...(this.skills[panelState.index] ?? newSkill()) }
					: newSkill();
		}
	}

	closePanel() {
		this.panelState = { kind: 'closed' };
	}

	saveAndClosePanel() {
		if (this.panelState.kind === 'mcpServer') {
			this.saveMcpServer(this.panelState);
		} else if (this.panelState.kind === 'skill') {
			this.saveSkill(this.panelState);
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

	private saveSkill(panelState: SkillPanelState) {
		const skill = {
			...this.skillDraft,
			name: this.skillDraft.name.trim(),
			description: this.skillDraft.description.trim()
		};

		if (skill.name.length === 0) {
			return;
		}

		if (panelState.mode === 'add') {
			this.skills = [...this.skills, skill];
		} else {
			this.skills = this.skills.map((currentSkill, index) =>
				index === panelState.index ? skill : currentSkill
			);
		}
	}

	removeSkill(index: number) {
		this.skills = this.skills.filter((_, currentIndex) => currentIndex !== index);
	}
}
