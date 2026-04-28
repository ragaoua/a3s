<script lang="ts">
	import FieldSet from './components/FieldSet.svelte';
	import FormField from './components/FormField.svelte';
	import RadioGroup from './components/RadioGroup.svelte';
	import SlideOverPanel from './components/SlideOverPanel.svelte';
	import { DeployAgentFormState } from './state/DeployAgentFormState.svelte';
	import McpServerPanelForm from './components/McpServerPanelForm.svelte';
	import SkillPanelForm from './components/SkillPanelForm.svelte';
	import SubagentPanelForm from './components/SubagentPanelForm.svelte';
	import ItemCardsList from './components/ItemCardsList.svelte';
	import { OUTBOUND_AUTH_MODE_LABELS, type OutboundAuthMode } from './types/outboundAuthConfig';

	const s = new DeployAgentFormState();
	const { form } = $props();

	const mcpServerAuthMismatch = $derived(
		s.authMode !== 'oauth2' &&
			s.panelState.kind === 'mcpServer' &&
			['oauth_token_forward', 'oauth_token_exchange'].includes(s.mcpServerDraft.authMode)
	);

	const subagentAuthMismatch = $derived(
		s.authMode !== 'oauth2' &&
			s.panelState.kind === 'subagent' &&
			['oauth_token_forward', 'oauth_token_exchange'].includes(s.subagentDraft.authMode)
	);

	const agentAuthMismatch = $derived(mcpServerAuthMismatch || subagentAuthMismatch);

  function buildAuthLabel(authMode: OutboundAuthMode): string {
    return `Auth: ${OUTBOUND_AUTH_MODE_LABELS[authMode]}`
  }
</script>

<main class="min-h-screen bg-transparent px-4 py-12 text-neutral-100">
	<div
		class="mx-auto w-full max-w-2xl rounded-2xl border border-neutral-800 bg-neutral-900/90 p-8 shadow-xl shadow-black/40 backdrop-blur-sm"
	>
		<h1 class="text-2xl font-semibold">Create Agent</h1>

		<form method="POST" class="mt-8 space-y-6">
			{#if form?.success}
				<div
					class="rounded-lg border border-emerald-600/70 bg-emerald-900/30 px-4 py-3 text-sm text-emerald-100"
				>
					<p class="font-semibold">Agent deployed successfully.</p>
					{#if form.agentApiKey}
						<p class="mt-1 font-mono break-all text-emerald-200">API key: {form.agentApiKey}</p>
					{/if}
				</div>
			{:else if form?.error}
				<div
					class="rounded-lg border border-orange-600/70 bg-orange-900/30 px-4 py-3 text-sm text-orange-100"
				>
					<p class="font-semibold">Error while deploying agent.</p>
					<p class="mt-1 font-mono break-all text-orange-200">{form.error}</p>
				</div>
			{/if}

			<FieldSet title="Agent">
				<FormField
					label="Agent name"
					id="agent-name"
					name="name"
					bind:value={s.agentName}
					placeholder="e.g. Support Assistant"
					required
				/>

				<FormField
					label="Description"
					id="description"
					name="description"
					bind:value={s.description}
					placeholder="Short summary of what this agent does."
					required
				/>

				<FormField
					label="Instructions"
					id="instructions"
					name="instructions"
					bind:value={s.instructions}
					placeholder="Describe behavior, goals, and constraints."
					isTextarea
					required
				/>
			</FieldSet>

			<ItemCardsList
				title="Skills"
				items={s.skills}
				primaryText={(skill) => skill.name}
				secondaryText={(skill) => skill.description}
				hiddenInputName="skills"
				addLabel="Add skill"
				onAdd={() => s.openPanel({ kind: 'skill', mode: 'add' })}
				onEdit={(index) => s.openPanel({ kind: 'skill', mode: 'edit', index })}
				onRemove={(index) => s.removeSkill(index)}
			/>

			<ItemCardsList
				title="Subagents"
				items={s.subagents}
				primaryText={(subagent) => `${subagent.name} (${subagent.type})`}
				secondaryText={(subagent) => buildAuthLabel(subagent.authMode)}
				hiddenInputName="subagents"
				addLabel="Add subagent"
				onAdd={() => s.openPanel({ kind: 'subagent', mode: 'add' })}
				onEdit={(index) => s.openPanel({ kind: 'subagent', mode: 'edit', index })}
				onRemove={(index) => s.removeSubagent(index)}
			/>

			<FieldSet title="Model">
				<FormField
					label="Model"
					id="model"
					name="model"
					bind:value={s.model}
					placeholder="e.g. gpt-5.3-codex, claude-opus-4.6, ..."
					required
				/>

				<FormField
					label="API URL"
					id="api-url"
					name="apiUrl"
					type="url"
					bind:value={s.apiUrl}
					placeholder="e.g. https://api.anthropic.com/v1/, https://local.myorg.llm/v1, ..."
					required
				/>

				<FormField
					label="API key"
					id="api-key"
					name="apiKey"
					type="password"
					bind:value={s.apiKey}
					placeholder="Enter API key"
					required
				/>
			</FieldSet>

			<FieldSet title="Authorization mode">
				<RadioGroup
					name="authMode"
					bind:group={s.authMode}
					choices={[
						{ value: 'apiKey', label: 'API key' },
						{ value: 'oauth2', label: 'OAuth2' },
						{ value: 'none', label: 'Disabled' }
					]}
				/>

				{#if s.authMode === 'apiKey'}
					<div class="flex gap-3">
						<span class="text-neutral-400">An API Key will be generated.</span>
					</div>
				{:else if s.authMode === 'oauth2'}
					<FormField
						label="OAuth2 issuer URL"
						id="oauth2-issuer-url"
						name="oauth2IssuerUrl"
						type="url"
						bind:value={s.oauth2IssuerUrl}
						required
					/>
				{:else}
					<div class="flex gap-3">
						<span class="text-neutral-400">Authentication will be disabled.</span>
					</div>
				{/if}
			</FieldSet>

			<ItemCardsList
				title="MCP Servers"
				items={s.mcpServers}
				primaryText={(mcpServer) => mcpServer.url}
				secondaryText={(mcpServer) => buildAuthLabel(mcpServer.authMode)}
				hiddenInputName="mcpServers"
				addLabel="Add MCP server"
				onAdd={() => s.openPanel({ kind: 'mcpServer', mode: 'add' })}
				onEdit={(index) => s.openPanel({ kind: 'mcpServer', mode: 'edit', index })}
				onRemove={(index) => s.removeMcpServer(index)}
			/>

			<button
				type="submit"
				class="w-full rounded-lg bg-neutral-200 px-4 py-2 text-sm font-semibold text-black transition hover:bg-white"
			>
				Deploy agent
			</button>
		</form>
	</div>
</main>

<SlideOverPanel
	open={s.panelState.kind !== 'closed'}
	title={s.panelTitle}
	actionLabel={s.panelActionLabel}
	actionDisabled={agentAuthMismatch}
	onClose={() => s.closePanel()}
	onAction={() => s.saveAndClosePanel()}
>
	{#if s.panelState.kind === 'mcpServer'}
		<McpServerPanelForm
			bind:mcpServerDraft={s.mcpServerDraft}
			agentAuthMismatch={mcpServerAuthMismatch}
		/>
	{:else if s.panelState.kind === 'skill'}
		<SkillPanelForm bind:skillDraft={s.skillDraft} />
	{:else if s.panelState.kind === 'subagent'}
		<SubagentPanelForm
			bind:subagentDraft={s.subagentDraft}
			agentAuthMismatch={subagentAuthMismatch}
		/>
	{/if}
</SlideOverPanel>
