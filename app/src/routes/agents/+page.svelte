<script lang="ts">
	const { data, form } = $props();

	const formatCreatedAt = (value: string) => {
		if (!value) return 'Unknown';
		return new Intl.DateTimeFormat(undefined, {
			dateStyle: 'medium',
			timeStyle: 'short'
		}).format(new Date(value));
	};

	const statusColor = (phase: string) => {
		switch (phase) {
			case 'Running':
				return 'text-emerald-300 border-emerald-700/70 bg-emerald-900/30';
			case 'Pending':
				return 'text-amber-300 border-amber-700/70 bg-amber-900/30';
			case 'Failed':
				return 'text-rose-300 border-rose-700/70 bg-rose-900/30';
			default:
				return 'text-neutral-300 border-neutral-700 bg-neutral-800/60';
		}
	};
</script>

<main class="min-h-screen bg-transparent px-4 py-12 text-neutral-100">
	<div
		class="mx-auto w-full max-w-4xl rounded-2xl border border-neutral-800 bg-neutral-900/90 p-8 shadow-xl shadow-black/40 backdrop-blur-sm"
	>
		<h1 class="text-2xl font-semibold">Agents</h1>
		<p class="mt-2 text-sm text-neutral-400">Currently deployed agent pods in Kubernetes.</p>

		{#if form?.error}
			<div
				class="mt-6 rounded-lg border border-orange-600/70 bg-orange-900/30 px-4 py-3 text-sm text-orange-100"
			>
				<p class="font-semibold">Error while deleting agent.</p>
				<p class="mt-1 font-mono break-all text-orange-200">{form.error}</p>
			</div>
		{/if}

		{#if data.agents.length === 0}
			<div class="mt-8 rounded-xl border border-neutral-800 bg-black/30 px-4 py-8 text-center">
				<p class="text-neutral-300">No deployed agents found.</p>
				<p class="mt-2 text-sm text-neutral-500">Deploy an agent from the Create Agent page.</p>
			</div>
		{:else}
			<ul class="mt-8 space-y-4">
				{#each data.agents as agent (agent)}
					<li class="rounded-xl border border-neutral-800 bg-black/30 p-4">
						<div class="flex flex-wrap items-start justify-between gap-3">
							<div>
								<h2 class="text-lg font-semibold text-neutral-100">{agent.agentName}</h2>
								<p class="mt-1 text-xs break-all text-neutral-500">{agent.podName}</p>
							</div>
							<div class="flex items-center gap-2">
								<span
									class={`rounded-full border px-3 py-1 text-xs font-semibold ${statusColor(agent.status)}`}
								>
									{agent.status}
								</span>
								<form method="POST" action="?/delete">
									<input type="hidden" name="podName" value={agent.podName} />
									<button
										type="submit"
										class="rounded-lg border border-rose-700/70 bg-rose-900/30 px-3 py-1 text-xs font-semibold text-rose-200 transition hover:bg-rose-900/60"
									>
										Delete
									</button>
								</form>
							</div>
						</div>
						<dl class="mt-4 grid gap-3 text-sm text-neutral-300 sm:grid-cols-3">
							<div>
								<dt class="text-xs tracking-wide text-neutral-500 uppercase">Created</dt>
								<dd class="mt-1">{formatCreatedAt(agent.createdAt)}</dd>
							</div>
						</dl>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</main>
