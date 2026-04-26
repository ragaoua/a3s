<script lang="ts">
	import FieldSet from './components/FieldSet.svelte';
	import FormField from './components/FormField.svelte';
	import RadioGroup from './components/RadioGroup.svelte';
	import { DeployAgentFormState } from './state/DeployAgentFormState.svelte.js';

	const s = new DeployAgentFormState();
	const { form } = $props();
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

			<FieldSet title="MCP Servers">
				{#each s.mcpServers as mcpServer, index (index)}
					<div
						class="flex flex-col gap-3 rounded-xl border border-neutral-700 bg-black/45 p-3 sm:flex-row sm:items-stretch sm:justify-between"
					>
						<div class="min-w-0 space-y-2">
							<p class="text-sm font-medium break-all text-neutral-100">
								{mcpServer}
							</p>
							<p class="text-sm text-neutral-300">No auth configured</p>
						</div>

						<div
							class="flex items-center justify-between gap-2 sm:flex-col sm:items-end sm:justify-between"
						>
							<button
								type="button"
								onclick={() => s.openPanel(index)}
								class="flex-1 rounded-lg border border-neutral-700 bg-neutral-900/80 px-3 py-1.5 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800 sm:w-24 sm:flex-none"
							>
								Edit
							</button>
							<button
								type="button"
								onclick={() => s.removeMcpServer(index)}
								class="flex-1 rounded-lg border border-red-900/80 bg-red-950/40 px-3 py-1.5 text-sm font-medium text-red-200 transition hover:bg-red-900/40 sm:w-24 sm:flex-none"
							>
								Remove
							</button>
						</div>

						<input type="hidden" name="mcpServers" value={mcpServer} />
					</div>
				{/each}

				<button
					type="button"
					onclick={() => s.openPanel()}
					class="rounded-lg bg-neutral-200 px-4 py-2 text-sm font-medium text-black transition hover:bg-white"
				>
					Add MCP server
				</button>
			</FieldSet>

			<button
				type="submit"
				class="w-full rounded-lg bg-neutral-200 px-4 py-2 text-sm font-semibold text-black transition hover:bg-white"
			>
				Deploy agent
			</button>
		</form>
	</div>
</main>

<div
	inert={!s.isPanelOpen}
	aria-hidden={!s.isPanelOpen}
	class={`fixed inset-0 z-40 ${s.isPanelOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}
>
	<button
		type="button"
		aria-label="Close MCP server panel"
		onclick={() => s.closePanel()}
		class={`absolute inset-0 bg-black/60 transition-opacity duration-300 ${s.isPanelOpen ? 'opacity-100' : 'opacity-0'}`}
	></button>

	<aside
		aria-label={s.editingMcpServerIndex === null ? 'Add MCP server' : 'Edit MCP server'}
		class={`absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-neutral-800 bg-neutral-900 p-6 shadow-2xl transition-transform duration-300 ease-in-out ${s.isPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}
	>
		<form
			class="flex h-full flex-col gap-4"
			onsubmit={(event) => {
				event.preventDefault();
				s.saveMcpServer();
			}}
		>
			<FormField
				label="MCP server URL"
				id="mcp-server-draft"
				name="mcpServerDraft"
				type="url"
				bind:value={s.mcpServerDraft}
				placeholder="https://example-mcp-server.com"
				required
			/>

			<div class="mt-auto flex gap-3">
				<button
					type="button"
					onclick={() => s.closePanel()}
					class="flex-1 rounded-lg border border-neutral-700 bg-black/45 px-4 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
				>
					Cancel
				</button>
				<button
					type="submit"
					class="flex-1 rounded-lg bg-neutral-200 px-4 py-2 text-sm font-medium text-black transition hover:bg-white"
				>
					{s.editingMcpServerIndex === null ? 'Add MCP server' : 'Update MCP server'}
				</button>
			</div>
		</form>
	</aside>
</div>
