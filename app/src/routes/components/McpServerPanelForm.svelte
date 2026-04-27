<script lang="ts">
	import { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';
	import {
		MCP_SERVER_AUTH_MODE_LABELS,
		MCP_SERVER_AUTH_MODE_OPTIONS,
		MCP_SERVER_OAUTH2_AUTH_METHOD_LABELS,
		type McpServer
	} from '../types/mcpServer';
	import FormField from './FormField.svelte';
	import HeadsUpCard from './HeadsUpCard.svelte';

	let {
		mcpServerDraft = $bindable(),
		agentAuthMismatch
	}: {
		mcpServerDraft: McpServer;
		agentAuthMismatch: boolean;
	} = $props();

	const tokenEndpointRequired = $derived(mcpServerDraft.authMode === 'oauth_client_credentials');
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

{#if mcpServerDraft.authMode === 'oauth_token_forward'}
	<HeadsUpCard>
		The inbound auth token your agent validates will be forwarded as-is to this MCP server.
	</HeadsUpCard>
{:else if mcpServerDraft.authMode === 'oauth_token_exchange'}
	<HeadsUpCard>
		The inbound auth token your agent validates will be exchanged for a new token.
	</HeadsUpCard>
{/if}

{#if agentAuthMismatch}
	<div
		class="rounded-lg border border-red-600/70 bg-red-900/25 px-4 py-3 text-sm text-red-100"
		role="alert"
	>
		<p class="font-semibold">Incompatible agent authorization mode</p>
		<p class="mt-1 text-red-100/90">
			{MCP_SERVER_AUTH_MODE_LABELS[mcpServerDraft.authMode]} requires the agent's authorization mode to
			be set to OAuth2. Update the agent's authorization mode, or pick a different MCP auth mode.
		</p>
	</div>
{/if}

{#if mcpServerDraft.authMode === 'oauth_client_credentials' || mcpServerDraft.authMode === 'oauth_token_exchange'}
	<FormField
		label="Client ID"
		id="mcp-server-client-id"
		name="mcpServerClientId"
		bind:value={mcpServerDraft.clientId}
		placeholder="Enter client ID"
		required
	/>

	<FormField
		label="Client secret"
		id="mcp-server-client-secret"
		name="mcpServerClientSecret"
		type="password"
		bind:value={mcpServerDraft.clientSecret}
		placeholder="Enter client secret"
		required
	/>

	<FormField
		label={tokenEndpointRequired ? 'Token endpoint' : 'Token endpoint (optional)'}
		id="mcp-server-token-endpoint"
		name="mcpServerTokenEndpoint"
		type="url"
		bind:value={mcpServerDraft.tokenEndpoint}
		placeholder="https://auth.example.com/oauth/token"
		required={tokenEndpointRequired}
	/>

	{#if mcpServerDraft.authMode === 'oauth_token_exchange'}
		<p class="text-xs text-neutral-400">
			If left blank, the token endpoint will be discovered from the agent's OAuth2 issuer.
		</p>
	{/if}

	<div class="w-full space-y-2">
		<label for="mcp-server-auth-method" class="text-sm font-medium">Auth method</label>
		<select
			id="mcp-server-auth-method"
			name="mcpServerAuthMethod"
			bind:value={mcpServerDraft.authMethod}
			class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
		>
			{#each OAUTH2_AUTH_METHOD_OPTIONS as authMethod (authMethod)}
				<option value={authMethod}>{MCP_SERVER_OAUTH2_AUTH_METHOD_LABELS[authMethod]}</option>
			{/each}
		</select>
	</div>
{/if}
