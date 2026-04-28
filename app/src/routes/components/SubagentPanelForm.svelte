<script lang="ts">
	import { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';
	import {
		SUBAGENT_AUTH_MODE_LABELS,
		SUBAGENT_AUTH_MODE_OPTIONS,
		SUBAGENT_OAUTH2_AUTH_METHOD_LABELS,
		SUBAGENT_TYPE_LABELS,
		SUBAGENT_TYPE_OPTIONS,
		type Subagent
	} from '../types/subagent';
	import FormField from './FormField.svelte';
	import HeadsUpCard from './HeadsUpCard.svelte';

	let {
		subagentDraft = $bindable(),
		agentAuthMismatch
	}: {
		subagentDraft: Subagent;
		agentAuthMismatch: boolean;
	} = $props();

	const tokenEndpointRequired = $derived(subagentDraft.authMode === 'oauth_client_credentials');
</script>

<FormField
	label="Subagent URL"
	id="subagent-draft"
	name="subagentDraft"
	type="url"
	bind:value={subagentDraft.url}
	placeholder="https://example-subagent.com"
	required
/>

<div class="w-full space-y-2">
	<label for="subagent-type" class="text-sm font-medium">Type</label>
	<select
		id="subagent-type"
		name="subagentTypeDraft"
		bind:value={subagentDraft.type}
		class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
	>
		{#each SUBAGENT_TYPE_OPTIONS as type (type)}
			<option value={type}>{SUBAGENT_TYPE_LABELS[type]}</option>
		{/each}
	</select>
</div>

<div class="w-full space-y-2">
	<label for="subagent-auth-mode" class="text-sm font-medium">Auth mode</label>
	<select
		id="subagent-auth-mode"
		name="subagentAuthModeDraft"
		bind:value={subagentDraft.authMode}
		class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
	>
		{#each SUBAGENT_AUTH_MODE_OPTIONS as authMode (authMode)}
			<option value={authMode}>{SUBAGENT_AUTH_MODE_LABELS[authMode]}</option>
		{/each}
	</select>
</div>

{#if subagentDraft.authMode === 'oauth_token_forward'}
	<HeadsUpCard>
		The inbound auth token your agent validates will be forwarded as-is to this subagent.
	</HeadsUpCard>
{:else if subagentDraft.authMode === 'oauth_token_exchange'}
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
			{SUBAGENT_AUTH_MODE_LABELS[subagentDraft.authMode]} requires the agent's authorization mode to be
			set to OAuth2. Update the agent's authorization mode, or pick a different subagent auth mode.
		</p>
	</div>
{/if}

{#if subagentDraft.authMode === 'oauth_client_credentials' || subagentDraft.authMode === 'oauth_token_exchange'}
	<FormField
		label="Client ID"
		id="subagent-client-id"
		name="subagentClientId"
		bind:value={subagentDraft.clientId}
		placeholder="Enter client ID"
		required
	/>

	<FormField
		label="Client secret"
		id="subagent-client-secret"
		name="subagentClientSecret"
		type="password"
		bind:value={subagentDraft.clientSecret}
		placeholder="Enter client secret"
		required
	/>

	<FormField
		label={tokenEndpointRequired ? 'Token endpoint' : 'Token endpoint (optional)'}
		id="subagent-token-endpoint"
		name="subagentTokenEndpoint"
		type="url"
		bind:value={subagentDraft.tokenEndpoint}
		placeholder="https://auth.example.com/oauth/token"
		required={tokenEndpointRequired}
	/>

	{#if subagentDraft.authMode === 'oauth_token_exchange'}
		<p class="text-xs text-neutral-400">
			If left blank, the token endpoint will be discovered from the agent's OAuth2 issuer.
		</p>
	{/if}

	<div class="w-full space-y-2">
		<label for="subagent-auth-method" class="text-sm font-medium">Auth method</label>
		<select
			id="subagent-auth-method"
			name="subagentAuthMethod"
			bind:value={subagentDraft.authMethod}
			class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
		>
			{#each OAUTH2_AUTH_METHOD_OPTIONS as authMethod (authMethod)}
				<option value={authMethod}>{SUBAGENT_OAUTH2_AUTH_METHOD_LABELS[authMethod]}</option>
			{/each}
		</select>
	</div>
{/if}
