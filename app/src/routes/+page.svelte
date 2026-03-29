<script lang="ts">
	import FieldSet from './components/FieldSet.svelte';
	import FormField from './components/FormField.svelte';
	import RadioGroup from './components/RadioGroup.svelte';
	import { DeployAgentFormState } from './state/DeployAgentFormState.svelte.js';

  const s = new DeployAgentFormState();
  const { form } = $props();

</script>

<main class="min-h-screen bg-transparent px-4 py-12 text-neutral-100">
	<div class="mx-auto w-full max-w-2xl rounded-2xl border border-neutral-800 bg-neutral-900/90 p-8 shadow-xl shadow-black/40 backdrop-blur-sm">
		<h1 class="text-2xl font-semibold">Create Agent</h1>

		<form method="POST" class="mt-8 space-y-6">
			{#if form?.success}
				<div class="rounded-lg border border-emerald-600/70 bg-emerald-900/30 px-4 py-3 text-sm text-emerald-100">
					<p class="font-semibold">Agent deployed successfully.</p>
					{#if form.agentApiKey}
						<p class="mt-1 break-all font-mono text-emerald-200">API key: {form.agentApiKey}</p>
					{/if}
				</div>
      {:else if form?.error}
				<div class="rounded-lg border border-orange-600/70 bg-orange-900/30 px-4 py-3 text-sm text-orange-100">
					<p class="font-semibold">Error while deploying agent.</p>
						<p class="mt-1 break-all font-mono text-orange-200">{form.error}</p>
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

      <FieldSet title="Authentication">
        <RadioGroup
          name="authMode"
          bind:group={s.authMode}
          choices={[
            { value: "apiKey", label: "API key" },
            { value: "oauth2", label: "OAuth2" },
            { value: "none", label: "Disabled" }
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

          <FormField
            label="OAuth2 audience"
            id="oauth2-audience"
            name="oauth2Audience"
            bind:value={s.oauth2Audience}
            placeholder="Audience claim to validate"
          />

          <FormField
            label="OAuth2 JWKS URL"
            id="oauth2-jwks-url"
            name="oauth2JwksUrl"
            type="url"
            bind:value={s.oauth2JwksUrl}
          />
        {:else}
          <div class="flex gap-3">
					<span class="text-neutral-400">Authentication will be disabled.</span>
				</div>
        {/if}
			</FieldSet>

      <FieldSet title="MCP Servers">
        {#each { length: s.mcpServers.length }, index}
					<div class="flex items-center gap-2">
            <FormField
              id={`mcp-server-${index}`}
              name="mcpServers"
              type="url"
              bind:value={s.mcpServers[index]}
							placeholder="https://example-mcp-server.com"
            />
						<button
							type="button"
							onclick={() => s.removeMcpServer(index)}
							class="rounded-lg border border-neutral-700 bg-black/45 px-3 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
						>
							Remove
						</button>
					</div>
				{/each}

				<button
					type="button"
					onclick={() => s.addMcpServer()}
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
