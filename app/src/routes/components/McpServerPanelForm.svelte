<script lang="ts">
	import type { McpServer } from '../types/mcpServer';
	import FormField from './FormField.svelte';
	import OutboundAuthConfigForm from './OutboundAuthConfigForm.svelte';

	let {
		mcpServerDraft = $bindable(),
		agentAuthMismatch
	}: {
		mcpServerDraft: McpServer;
		agentAuthMismatch: boolean;
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

<OutboundAuthConfigForm
	bind:auth={mcpServerDraft}
	subjectLabel="MCP server"
	idPrefix="mcp-server"
	namePrefix="mcpServer"
	{agentAuthMismatch}
	allowedAuthModes={[
		'none',
		'oauth_client_credentials',
		'oauth_token_forward',
		'oauth_token_exchange'
	]}
/>
