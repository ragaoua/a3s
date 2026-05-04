<script lang="ts">
	import {
		OAUTH2_ENDPOINT_SOURCE_LABELS,
		OAUTH2_ENDPOINT_SOURCE_OPTIONS,
		type Oauth2JwtPolicy
	} from '../types/oauth2Policies';
	import FormField from './FormField.svelte';
	import RadioGroup from './RadioGroup.svelte';

	let {
		jwtDraft = $bindable(),
		onAddClaim,
		onRemoveClaim
	}: {
		jwtDraft: Oauth2JwtPolicy;
		onAddClaim: () => void;
		onRemoveClaim: (index: number) => void;
	} = $props();

	const checkboxLabelClass =
		'flex cursor-pointer items-center gap-2 rounded-lg border border-neutral-700 bg-black/45 px-3 py-2 text-sm text-neutral-200';
</script>

<div class="w-full space-y-2">
	<span class="text-sm font-medium">JWKS source</span>
	<RadioGroup
		name="oauth2JwtJwksSource"
		bind:group={jwtDraft.jwksSource}
		choices={OAUTH2_ENDPOINT_SOURCE_OPTIONS.map((source) => ({
			value: source,
			label: OAUTH2_ENDPOINT_SOURCE_LABELS[source]
		}))}
	/>
</div>

{#if jwtDraft.jwksSource === 'static'}
	<FormField
		label="JWKS URL"
		id="oauth2-jwt-jwks-url"
		name="oauth2JwtJwksUrl"
		type="url"
		bind:value={jwtDraft.jwksUrl}
		placeholder="https://auth.example.com/.well-known/jwks.json"
		required
	/>
{/if}

<div class="flex items-center justify-between gap-3">
	<p class="text-sm font-medium text-neutral-100">RFC 9068 claims validation</p>
	<label class={checkboxLabelClass}>
		<input
			type="checkbox"
			class="accent-neutral-300"
			bind:checked={jwtDraft.rfc9068Enabled}
		/>
		<span>Enabled</span>
	</label>
</div>

{#if jwtDraft.rfc9068Enabled}
	<FormField
		label="Resource server"
		id="oauth2-jwt-rfc9068-resource-server"
		name="oauth2JwtRfc9068ResourceServer"
		bind:value={jwtDraft.rfc9068ResourceServer}
		placeholder="my_resource_server_identifier"
		required
	/>
{/if}

<div class="space-y-2">
	<p class="text-sm font-medium text-neutral-100">Required claims</p>
	<p class="text-xs text-neutral-400">
		Tokens are accepted only when each claim matches the configured value.
	</p>

	{#each jwtDraft.claims as claim, index (index)}
		<div class="flex flex-col gap-2 sm:flex-row sm:items-end">
			<div class="flex-1">
				<FormField
					label={index === 0 ? 'Claim' : undefined}
					id="oauth2-jwt-claim-key-{index}"
					name="oauth2JwtClaimKey"
					bind:value={claim.key}
					placeholder="e.g. scope"
					required
				/>
			</div>
			<div class="flex-1">
				<FormField
					label={index === 0 ? 'Expected value' : undefined}
					id="oauth2-jwt-claim-value-{index}"
					name="oauth2JwtClaimValue"
					bind:value={claim.value}
					placeholder="e.g. read"
					required
				/>
			</div>
			<button
				type="button"
				onclick={() => onRemoveClaim(index)}
				class="rounded-lg border border-red-900/80 bg-red-950/40 px-3 py-2 text-sm font-medium text-red-200 transition hover:bg-red-900/40 sm:w-24"
			>
				Remove
			</button>
		</div>
	{/each}

	<button
		type="button"
		onclick={onAddClaim}
		class="rounded-lg border border-neutral-700 bg-neutral-900/80 px-3 py-1.5 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
	>
		Add claim
	</button>
</div>
