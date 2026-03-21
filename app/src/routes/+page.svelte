<script lang="ts">
  let model = '';
	let agentName = '';
	let description = '';
	let instructions = '';
	let apiKey = '';
	let apiUrl = '';
	import FieldSet from './components/FieldSet.svelte';
	import FormField from './components/FormField.svelte';
	import RadioGroup from './components/RadioGroup.svelte';

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

<main class="min-h-screen bg-transparent px-4 py-12 text-neutral-100">
	<div class="mx-auto w-full max-w-2xl rounded-2xl border border-neutral-800 bg-neutral-900/90 p-8 shadow-xl shadow-black/40 backdrop-blur-sm">
		<h1 class="text-2xl font-semibold">Create Agent</h1>

		<form method="POST" class="mt-8 space-y-6">
      <FieldSet title="Agent">
        <FormField
          label="Agent name"
          id="agent-name"
          name="name"
          bind:value={agentName}
          placeholder="e.g. Support Assistant"
          required
        />

        <FormField
          label="Description"
          id="description"
          name="description"
          bind:value={description}
          placeholder="Short summary of what this agent does."
          required
        />

        <FormField
          label="Instructions"
          id="instructions"
          name="instructions"
          bind:value={instructions}
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
          bind:value={model}
          placeholder="e.g. gpt-5.3-codex, claude-opus-4.6, ..."
          required
        />

        <FormField
          label="API URL"
          id="api-url"
          name="apiUrl"
          type="url"
          bind:value={apiUrl}
          placeholder="e.g. https://api.anthropic.com/v1/, https://local.myorg.llm/v1, ..."
          required
        />

        <FormField
          label="API key"
          id="api-key"
          name="apiKey"
          type="password"
          bind:value={apiKey}
          placeholder="Enter API key"
          required
        />
			</FieldSet>

      <FieldSet title="Authentication">
        <RadioGroup
          name="authMode"
          bind:group={authMode}
          choices={[
            { value: "apiKey", label: "API key" },
            { value: "oauth2", label: "OAuth2" }
          ]}
        />

        {#if authMode === 'apiKey'}
          <div class="flex gap-3">
					<span class="text-neutral-400">An API Key will be generated.</span>
				</div>
        {:else}
          <FormField
            label="OAuth2 issuer URL"
            id="oauth2-issuer-url"
            name="oauth2IssuerUrl"
            type="url"
            bind:value={oauth2IssuerUrl}
            required
          />

          <FormField
            label="OAuth2 JWKS URL"
            id="oauth2-jwks-url"
            name="oauth2JwksUrl"
            type="url"
            bind:value={oauth2JwksUrl}
          />
        {/if}
			</FieldSet>

      <FieldSet title="MCP Servers">
        {#each { length: mcpServers.length }, index}
					<div class="flex items-center gap-2">
            <FormField
              id={`mcp-server-${index}`}
              name="mcpServers"
              type="url"
              bind:value={mcpServers[index]}
							placeholder="https://example-mcp-server.com"
            />
						<button
							type="button"
							onclick={() => removeMcpServer(index)}
							class="rounded-lg border border-neutral-700 bg-black/45 px-3 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
						>
							Remove
						</button>
					</div>
				{/each}

				<button
					type="button"
					onclick={addMcpServer}
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
