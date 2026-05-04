<script lang="ts">
	import { OAUTH2_AUTH_METHOD_OPTIONS } from '$lib/types/agentRuntimeConfig/outboundAuth';
	import {
		OAUTH2_ENDPOINT_SOURCE_LABELS,
		OAUTH2_ENDPOINT_SOURCE_OPTIONS,
		OAUTH2_INTROSPECTION_AUTH_METHOD_LABELS,
		type Oauth2IntrospectionPolicy
	} from '../types/oauth2Policies';
	import FormField from './FormField.svelte';
	import RadioGroup from './RadioGroup.svelte';

	let {
		introspectionDraft = $bindable()
	}: {
		introspectionDraft: Oauth2IntrospectionPolicy;
	} = $props();
</script>

<div class="w-full space-y-2">
	<span class="text-sm font-medium">Introspection endpoint</span>
	<RadioGroup
		name="oauth2IntrospectionEndpointSource"
		bind:group={introspectionDraft.endpointSource}
		choices={OAUTH2_ENDPOINT_SOURCE_OPTIONS.map((source) => ({
			value: source,
			label: OAUTH2_ENDPOINT_SOURCE_LABELS[source]
		}))}
	/>
</div>

{#if introspectionDraft.endpointSource === 'static'}
	<FormField
		label="Endpoint URL"
		id="oauth2-introspection-endpoint"
		name="oauth2IntrospectionEndpoint"
		type="url"
		bind:value={introspectionDraft.endpoint}
		placeholder="https://auth.example.com/oauth/introspect"
		required
	/>
{/if}

<FormField
	label="Client ID"
	id="oauth2-introspection-client-id"
	name="oauth2IntrospectionClientId"
	bind:value={introspectionDraft.clientId}
	placeholder="Enter client ID"
	required
/>

<FormField
	label="Client secret"
	id="oauth2-introspection-client-secret"
	name="oauth2IntrospectionClientSecret"
	type="password"
	bind:value={introspectionDraft.clientSecret}
	placeholder="Enter client secret"
	required
/>

<div class="w-full space-y-2">
	<label for="oauth2-introspection-auth-method" class="text-sm font-medium">Auth method</label>
	<select
		id="oauth2-introspection-auth-method"
		name="oauth2IntrospectionAuthMethod"
		bind:value={introspectionDraft.authMethod}
		class="w-full rounded-lg border border-neutral-700 bg-black/50 px-3 py-2 text-sm text-neutral-100 transition outline-none focus:border-neutral-300"
	>
		{#each OAUTH2_AUTH_METHOD_OPTIONS as authMethod (authMethod)}
			<option value={authMethod}>{OAUTH2_INTROSPECTION_AUTH_METHOD_LABELS[authMethod]}</option>
		{/each}
	</select>
</div>
