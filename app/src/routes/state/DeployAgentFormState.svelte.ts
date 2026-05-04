import { newMcpServer, type McpServer } from '../types/mcpServer';
import {
	newOauth2IntrospectionPolicy,
	newOauth2JwtPolicy,
	newOauth2PoliciesConfig,
	type Oauth2IntrospectionPolicy,
	type Oauth2JwtPolicy,
	type Oauth2PoliciesConfig
} from '../types/oauth2Policies';
import { newSkill, type Skill } from '../types/skill';
import { newSubagent, type Subagent } from '../types/subagent';
import type {
	AnyOpenPanelState,
	ClosedPanelState,
	McpServerPanelState,
	SkillPanelState,
	SubagentPanelState
} from '../types/slideOverPanel';

const KIND_LABEL = {
	mcpServer: 'MCP server',
	skill: 'skill',
	subagent: 'subagent',
	oauth2Jwt: 'JWT validation policy',
	oauth2Introspection: 'introspection policy'
} as const;

export class DeployAgentFormState {
	agentName: string = $state('');
	description: string = $state('');
	instructions: string = $state('');

	model: string = $state('');
	apiUrl: string = $state('');
	apiKey: string = $state('');

	authMode: 'apiKey' | 'oauth2' | 'none' = $state('apiKey');
	oauth2IssuerUrl = $state('');
	oauth2Policies: Oauth2PoliciesConfig = $state(newOauth2PoliciesConfig());

	oauth2JwtDraft: Oauth2JwtPolicy = $state(newOauth2JwtPolicy());
	oauth2IntrospectionDraft: Oauth2IntrospectionPolicy = $state(newOauth2IntrospectionPolicy());

	addOauth2JwtClaimDraft() {
		this.oauth2JwtDraft.claims = [...this.oauth2JwtDraft.claims, { key: '', value: '' }];
	}

	removeOauth2JwtClaimDraft(index: number) {
		this.oauth2JwtDraft.claims = this.oauth2JwtDraft.claims.filter(
			(_, currentIndex) => currentIndex !== index
		);
	}

	disableOauth2Jwt() {
		this.oauth2Policies.jwtEnabled = false;
	}

	disableOauth2Introspection() {
		this.oauth2Policies.introspectionEnabled = false;
	}

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

		const subject = KIND_LABEL[this.panelState.kind];

		if (this.panelState.kind === 'oauth2Jwt' || this.panelState.kind === 'oauth2Introspection') {
			return `Configure ${subject}`;
		}

		return `${this.panelState.mode === 'add' ? 'Add' : 'Edit'} ${subject}`;
	});

	panelActionLabel = $derived.by(() => {
		if (this.panelState.kind === 'closed') {
			return '';
		}

		const subject = KIND_LABEL[this.panelState.kind];

		if (this.panelState.kind === 'oauth2Jwt' || this.panelState.kind === 'oauth2Introspection') {
			return `Save ${subject}`;
		}

		return `${this.panelState.mode === 'add' ? 'Add' : 'Update'} ${subject}`;
	});

	openPanel(panelState: AnyOpenPanelState) {
		this.panelState = panelState;

		switch (panelState.kind) {
			case 'mcpServer':
				this.mcpServerDraft =
					panelState.mode === 'edit'
						? { ...(this.mcpServers[panelState.index] ?? newMcpServer()) }
						: newMcpServer();
				break;
			case 'skill':
				this.skillDraft =
					panelState.mode === 'edit'
						? { ...(this.skills[panelState.index] ?? newSkill()) }
						: newSkill();
				break;
			case 'subagent':
				this.subagentDraft =
					panelState.mode === 'edit'
						? { ...(this.subagents[panelState.index] ?? newSubagent()) }
						: newSubagent();
				break;
			case 'oauth2Jwt':
				this.oauth2JwtDraft = {
					...this.oauth2Policies.jwt,
					claims: this.oauth2Policies.jwt.claims.map((claim) => ({ ...claim }))
				};
				break;
			case 'oauth2Introspection':
				this.oauth2IntrospectionDraft = { ...this.oauth2Policies.introspection };
				break;
		}
	}

	closePanel() {
		this.panelState = { kind: 'closed' };
	}

	saveAndClosePanel() {
		switch (this.panelState.kind) {
			case 'mcpServer':
				this.saveMcpServer(this.panelState);
				break;
			case 'skill':
				this.saveSkill(this.panelState);
				break;
			case 'subagent':
				this.saveSubagent(this.panelState);
				break;
			case 'oauth2Jwt':
				this.saveOauth2Jwt();
				break;
			case 'oauth2Introspection':
				this.saveOauth2Introspection();
				break;
		}

		this.closePanel();
	}

	private saveOauth2Jwt() {
		this.oauth2Policies.jwt = {
			...this.oauth2JwtDraft,
			rfc9068ResourceServer: this.oauth2JwtDraft.rfc9068ResourceServer.trim(),
			jwksUrl: this.oauth2JwtDraft.jwksUrl.trim(),
			claims: this.oauth2JwtDraft.claims.map((claim) => ({
				key: claim.key.trim(),
				value: claim.value.trim()
			}))
		};
		this.oauth2Policies.jwtEnabled = true;
	}

	private saveOauth2Introspection() {
		this.oauth2Policies.introspection = {
			...this.oauth2IntrospectionDraft,
			endpoint: this.oauth2IntrospectionDraft.endpoint.trim(),
			clientId: this.oauth2IntrospectionDraft.clientId.trim(),
			clientSecret: this.oauth2IntrospectionDraft.clientSecret
		};
		this.oauth2Policies.introspectionEnabled = true;
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
