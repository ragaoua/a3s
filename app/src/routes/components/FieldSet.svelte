<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children, title }: { children: Snippet<[]>; title: string } = $props();
</script>

<fieldset class="space-y-3">
	<legend class="text-lg font-medium">{title}</legend>
	{@render children()}
</fieldset>
