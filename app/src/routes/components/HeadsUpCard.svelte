<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet<[]> } = $props();
</script>

<div
	class="rounded-lg border border-amber-600/70 bg-amber-900/20 px-4 py-3 text-sm text-amber-100"
	role="status"
>
	<p class="font-semibold">Heads up</p>
	<p class="mt-1 text-amber-100/90">
		{@render children()}
	</p>
</div>
