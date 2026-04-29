import { newMcpServer, type McpServer } from '../types/mcpServer';
import { newSkill, type Skill } from '../types/skill';
import { newSubagent, type Subagent } from '../types/subagent';
import type {
	AnyOpenPanelState,
	ClosedPanelState,
	McpServerPanelState,
	SkillPanelState,
	SubagentPanelState
} from '../types/slideOverPanel';

const KIND_LABEL = { mcpServer: 'MCP server', skill: 'skill', subagent: 'subagent' } as const;

export class DeployAgentFormState {
	agentName: string = $state('');
	description: string = $state('');
	instructions: string = $state('');

	model: string = $state('');
	apiUrl: string = $state('');
	apiKey: string = $state('');

	authMode: 'apiKey' | 'oauth2' | 'none' = $state('apiKey');
	oauth2IssuerUrl = $state('');

	mcpServers: McpServer[] = $state([]);
	mcpServerDraft: McpServer = $state(newMcpServer());

	skills: Skill[] = $state([]);
	skillDraft: Skill = $state(newSkill());

	subagents: Subagent[] = $state([]);
	subagentDraft: Subagent = $state(newSubagent());

	panelState: ClosedPanelState | AnyOpenPanelState = $state({ kind: 'closed' });

	panelTitle = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		const title = `${this.panelState.mode === 'add' ? 'Add' : 'Edit'} ${KIND_LABEL[this.panelState.kind]}`;
		return title;
	});

	panelActionLabel = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		const title = `${this.panelState.mode === 'add' ? 'Add' : 'Update'} ${KIND_LABEL[this.panelState.kind]}`;
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
		} else if (panelState.kind === 'subagent') {
			this.subagentDraft =
				panelState.mode === 'edit'
					? { ...(this.subagents[panelState.index] ?? newSubagent()) }
					: newSubagent();
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
		} else if (this.panelState.kind === 'subagent') {
			this.saveSubagent(this.panelState);
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

	private saveSubagent(panelState: SubagentPanelState) {
		const subagent = {
			...this.subagentDraft,
			name: this.subagentDraft.name.trim(),
			url: this.subagentDraft.url.trim()
		};

		if (subagent.name.length === 0 || subagent.url.length === 0) {
			return;
		}

		if (panelState.mode === 'add') {
			this.subagents = [...this.subagents, subagent];
		} else {
			this.subagents = this.subagents.map((currentSubagent, index) =>
				index === panelState.index ? subagent : currentSubagent
			);
		}
	}

	removeSubagent(index: number) {
		this.subagents = this.subagents.filter((_, currentIndex) => currentIndex !== index);
	}
}
