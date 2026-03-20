<script lang="ts">
  let model = '';
	let agentName = '';
	let description = '';
	let instructions = '';
	let apiKey = '';
	let apiUrl = '';
	let mcpServers: string[] = [''];
  let oauth2IssuerUrl = '';
  let oauth2JwksUrl = '';
	let authMode: 'apiKey' | 'oauth2' = 'apiKey';

	const addMcpServer = () => {
		mcpServers = [...mcpServers, ''];
	};

	const removeMcpServer = (index: number) => {
		if (mcpServers.length === 1) {
			mcpServers = [''];
			return;
		}

		mcpServers = mcpServers.filter((_, currentIndex) => currentIndex !== index);
	};

</script>

<main class="min-h-screen bg-slate-100 px-4 py-12 text-slate-900">
	<div class="mx-auto w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
		<h1 class="text-2xl font-semibold">Create Agent</h1>
		<p class="mt-2 text-sm text-slate-600">Define your agent and the MCP servers it can reach.</p>

		<form method="POST" class="mt-8 space-y-6">
			<div class="space-y-2">
				<label for="model" class="text-sm font-medium">Model</label>
				<input
					id="model"
					name="model"
					type="text"
					bind:value={model}
					placeholder="e.g. Support Assistant"
					required
					class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
				/>
			</div>

			<div class="space-y-2">
				<label for="agent-name" class="text-sm font-medium">Agent name</label>
				<input
					id="agent-name"
					name="name"
					type="text"
					bind:value={agentName}
					placeholder="e.g. Support Assistant"
					required
					class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
				/>
			</div>

			<div class="space-y-2">
				<label for="instructions" class="text-sm font-medium">Instructions</label>
				<textarea
					id="instructions"
					name="instructions"
					rows="5"
					bind:value={instructions}
					placeholder="Describe behavior, goals, and constraints."
					required
					class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
				></textarea>
			</div>

			<div class="space-y-2">
				<label for="description" class="text-sm font-medium">Description</label>
				<textarea
					id="description"
					name="description"
					rows="3"
					bind:value={description}
					placeholder="Short summary of what this agent does."
					required
					class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
				></textarea>
			</div>

			<div class="space-y-2">
				<label for="api-url" class="text-sm font-medium">API URL</label>
				<input
					id="api-url"
					type="url"
					value={apiUrl}
          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
				/>
				<input type="hidden" name="apiUrl" value={apiUrl} />
			</div>

      <div class="space-y-2">
        <label for="api-key" class="text-sm font-medium">API key</label>
        <input
          id="api-key"
          name="apiKey"
          type="password"
          bind:value={apiKey}
          placeholder="Enter API key"
          required
          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
        />
      </div>
			<fieldset class="space-y-3">
				<legend class="text-sm font-medium">Authentication</legend>
				<div class="flex gap-3">
					<label class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm">
						<input type="radio" name="authMode" value="apiKey" bind:group={authMode} />
						<span>API key</span>
					</label>
					<label class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm">
						<input type="radio" name="authMode" value="oauth2" bind:group={authMode} />
						<span>OAuth2</span>
					</label>
				</div>
			</fieldset>

			{#if authMode === 'apiKey'}
				<div class="flex gap-3">
          <span>An API Key will be generated.</span>
        </div>
			{:else}
				<div class="space-y-2">
					<label for="oauth2-issuer-url" class="text-sm font-medium">OAuth2 issuer URL</label>
					<input
						id="oauth2-issuer-url"
						name="oauth2IssuerUrl"
						type="url"
						bind:value={oauth2IssuerUrl}
						required={authMode === 'oauth2'}
            class="w-full cursor-not-allowed rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm text-slate-600"
					/>
				</div>

				<div class="space-y-2">
					<label for="oauth2-jwks-url" class="text-sm font-medium">OAuth2 JWKS URL</label>
					<input
						id="oauth2-jwks-url"
						name="oauth2JwksUrl"
						type="url"
						bind:value={oauth2JwksUrl}
            class="w-full cursor-not-allowed rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm text-slate-600"
					/>
				</div>
			{/if}

			<fieldset class="space-y-3">
				<legend class="text-sm font-medium">MCP servers</legend>
        {#each { length: mcpServers.length }, index}
					<div class="flex items-center gap-2">
						<input
							type="url"
							name="mcpServers"
							bind:value={mcpServers[index]}
							placeholder="https://example-mcp-server.com"
							class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-slate-500"
						/>
						<button
							type="button"
							onclick={() => removeMcpServer(index)}
							class="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
						>
							Remove
						</button>
					</div>
				{/each}

				<button
					type="button"
					onclick={addMcpServer}
					class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
				>
					Add MCP server
				</button>
			</fieldset>

			<button
				type="submit"
				class="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
			>
				Deploy agent
			</button>
		</form>
	</div>
</main>
