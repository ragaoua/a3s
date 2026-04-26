<script lang="ts">
	import {
		MCP_SERVER_AUTH_MODE_LABELS,
		MCP_SERVER_AUTH_MODE_OPTIONS,
		type McpServer
	} from '../types/mcpServer';
	import FormField from './FormField.svelte';

	let {
		mcpServerDraft = $bindable()
	}: {
		mcpServerDraft: McpServer;
	} = $props();
</script>

<FormField
	label="MCP server URL"
	id="mcp-server-draft"
	name="mcpServerDraft"
	type="url"
	bind:value={mcpServerDraft.url}
	placeholder="https://example-mcp-server.com"
	required
/>

<div class="w-full space-y-2">
	<label for="mcp-server-auth-mode" class="text-sm font-medium">Auth mode</label>
	<select
		id="mcp-server-auth-mode"
		name="mcpServerAuthModeDraft"
		bind:value={mcpServerDraft.authMode}
		class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
	>
		{#each MCP_SERVER_AUTH_MODE_OPTIONS as authMode (authMode)}
			<option value={authMode}>{MCP_SERVER_AUTH_MODE_LABELS[authMode]}</option>
		{/each}
	</select>
</div>
