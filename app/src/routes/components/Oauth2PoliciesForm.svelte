<script lang="ts">
	import {
		OAUTH2_ENDPOINT_SOURCE_LABELS,
		OAUTH2_INTROSPECTION_AUTH_METHOD_LABELS,
		type Oauth2PoliciesConfig
	} from '../types/oauth2Policies';

	let {
		policies,
		onConfigureJwt,
		onDisableJwt,
		onConfigureIntrospection,
		onDisableIntrospection
	}: {
		policies: Oauth2PoliciesConfig;
		onConfigureJwt: () => void;
		onDisableJwt: () => void;
		onConfigureIntrospection: () => void;
		onDisableIntrospection: () => void;
	} = $props();

	const noPolicyEnabled = $derived(!policies.jwtEnabled && !policies.introspectionEnabled);

	const jwtSummary = $derived.by(() => {
		const jwks = `JWKS: ${OAUTH2_ENDPOINT_SOURCE_LABELS[policies.jwt.jwksSource].toLowerCase()}`;
		const rfc9068 = `RFC 9068: ${policies.jwt.rfc9068Enabled ? 'on' : 'off'}`;
		const claimCount = policies.jwt.claims.length;
		const claims = `${claimCount} required ${claimCount === 1 ? 'claim' : 'claims'}`;
		return [jwks, rfc9068, claims].join(' • ');
	});

	const introspectionSummary = $derived.by(() => {
		const endpoint = `Endpoint: ${OAUTH2_ENDPOINT_SOURCE_LABELS[policies.introspection.endpointSource].toLowerCase()}`;
		const authMethod = `Auth: ${OAUTH2_INTROSPECTION_AUTH_METHOD_LABELS[policies.introspection.authMethod]}`;
		return [endpoint, authMethod].join(' • ');
	});

	const cardClass =
		'flex flex-col gap-3 rounded-xl border border-neutral-700 bg-black/45 p-3 sm:flex-row sm:items-stretch sm:justify-between';
	const primaryButtonClass =
		'rounded-lg bg-neutral-200 px-3 py-1.5 text-sm font-medium text-black transition hover:bg-white sm:w-28';
	const secondaryButtonClass =
		'rounded-lg border border-neutral-700 bg-neutral-900/80 px-3 py-1.5 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800 sm:w-24';
	const dangerButtonClass =
		'rounded-lg border border-red-900/80 bg-red-950/40 px-3 py-1.5 text-sm font-medium text-red-200 transition hover:bg-red-900/40 sm:w-24';
</script>

<div class="space-y-3">
	<p class="text-sm font-medium text-neutral-100">Token validation policies</p>
	<p class="text-xs text-neutral-400">
		Pick how inbound tokens are validated. At least one policy must be enabled.
	</p>

	{#if noPolicyEnabled}
		<div
			class="rounded-lg border border-red-600/70 bg-red-900/25 px-4 py-3 text-sm text-red-100"
			role="alert"
		>
			<p class="font-semibold">No policy enabled</p>
			<p class="mt-1 text-red-100/90">Configure JWT validation, introspection, or both.</p>
		</div>
	{/if}

	<div class={cardClass}>
		<div class="min-w-0 space-y-2">
			<p class="text-sm font-medium break-all text-neutral-100">JWT validation</p>
			<p class="text-sm text-neutral-300">
				{policies.jwtEnabled ? jwtSummary : 'Not configured.'}
			</p>
		</div>

		<div
			class="flex items-center justify-between gap-2 sm:flex-col sm:items-end sm:justify-between"
		>
			{#if policies.jwtEnabled}
				<button type="button" onclick={onConfigureJwt} class={secondaryButtonClass}>
					Edit
				</button>
				<button type="button" onclick={onDisableJwt} class={dangerButtonClass}>
					Disable
				</button>
			{:else}
				<button type="button" onclick={onConfigureJwt} class={primaryButtonClass}>
					Configure
				</button>
			{/if}
		</div>
	</div>

	<div class={cardClass}>
		<div class="min-w-0 space-y-2">
			<p class="text-sm font-medium break-all text-neutral-100">Token introspection</p>
			<p class="text-sm text-neutral-300">
				{policies.introspectionEnabled ? introspectionSummary : 'Not configured.'}
			</p>
		</div>

		<div
			class="flex items-center justify-between gap-2 sm:flex-col sm:items-end sm:justify-between"
		>
			{#if policies.introspectionEnabled}
				<button type="button" onclick={onConfigureIntrospection} class={secondaryButtonClass}>
					Edit
				</button>
				<button type="button" onclick={onDisableIntrospection} class={dangerButtonClass}>
					Disable
				</button>
			{:else}
				<button type="button" onclick={onConfigureIntrospection} class={primaryButtonClass}>
					Configure
				</button>
			{/if}
		</div>
	</div>
</div>
