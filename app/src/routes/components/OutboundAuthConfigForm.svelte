<script lang="ts">
	import { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';
	import {
		OUTBOUND_AUTH_MODE_LABELS,
		OUTBOUND_AUTH_MODE_OPTIONS,
		OUTBOUND_OAUTH2_AUTH_METHOD_LABELS,
		type OutboundAuthConfig,
		type OutboundAuthMode
	} from '../types/outboundAuthConfig';
	import FormField from './FormField.svelte';
	import HeadsUpCard from './HeadsUpCard.svelte';

	let {
		auth = $bindable(),
		subjectLabel,
		idPrefix,
		namePrefix,
		agentAuthMismatch,
		allowedAuthModes = OUTBOUND_AUTH_MODE_OPTIONS
	}: {
		auth: OutboundAuthConfig;
		subjectLabel: string;
		idPrefix: string;
		namePrefix: string;
		agentAuthMismatch: boolean;
		allowedAuthModes?: readonly OutboundAuthMode[];
	} = $props();

	const tokenEndpointRequired = $derived(auth.authMode === 'oauth_client_credentials');
</script>

<div class="w-full space-y-2">
	<label for="{idPrefix}-auth-mode" class="text-sm font-medium">Auth mode</label>
	<select
		id="{idPrefix}-auth-mode"
		name="{namePrefix}AuthModeDraft"
		bind:value={auth.authMode}
		class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
	>
		{#each allowedAuthModes as authMode (authMode)}
			<option value={authMode}>{OUTBOUND_AUTH_MODE_LABELS[authMode]}</option>
		{/each}
	</select>
</div>

{#if auth.authMode === 'oauth_token_forward'}
	<HeadsUpCard>
		The inbound auth token your agent validates will be forwarded as-is to this {subjectLabel}.
	</HeadsUpCard>
{:else if auth.authMode === 'oauth_token_exchange'}
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
			{OUTBOUND_AUTH_MODE_LABELS[auth.authMode]} requires the agent's authorization mode to be set to
			OAuth2. Update the agent's authorization mode, or pick a different {subjectLabel} auth mode.
		</p>
	</div>
{/if}

{#if auth.authMode === 'oauth_client_credentials' || auth.authMode === 'oauth_token_exchange'}
	<FormField
		label="Client ID"
		id="{idPrefix}-client-id"
		name="{namePrefix}ClientId"
		bind:value={auth.clientId}
		placeholder="Enter client ID"
		required
	/>

	<FormField
		label="Client secret"
		id="{idPrefix}-client-secret"
		name="{namePrefix}ClientSecret"
		type="password"
		bind:value={auth.clientSecret}
		placeholder="Enter client secret"
		required
	/>

	<FormField
		label={tokenEndpointRequired ? 'Token endpoint' : 'Token endpoint (optional)'}
		id="{idPrefix}-token-endpoint"
		name="{namePrefix}TokenEndpoint"
		type="url"
		bind:value={auth.tokenEndpoint}
		placeholder="https://auth.example.com/oauth/token"
		required={tokenEndpointRequired}
	/>

	{#if auth.authMode === 'oauth_token_exchange'}
		<p class="text-xs text-neutral-400">
			If left blank, the token endpoint will be discovered from the agent's OAuth2 issuer.
		</p>
	{/if}

	<div class="w-full space-y-2">
		<label for="{idPrefix}-auth-method" class="text-sm font-medium">Auth method</label>
		<select
			id="{idPrefix}-auth-method"
			name="{namePrefix}AuthMethod"
			bind:value={auth.authMethod}
			class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
		>
			{#each OAUTH2_AUTH_METHOD_OPTIONS as authMethod (authMethod)}
				<option value={authMethod}>{OUTBOUND_OAUTH2_AUTH_METHOD_LABELS[authMethod]}</option>
			{/each}
		</select>
	</div>
{:else if auth.authMode === 'apiKey'}
	<FormField
		label="API key"
		id="{idPrefix}-api-key"
		name="{namePrefix}ApiKey"
		type="password"
		bind:value={auth.apiKey}
		placeholder="Enter API key"
		required
	/>
{/if}
