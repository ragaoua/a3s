<script lang="ts" generics="T">
	import FieldSet from './FieldSet.svelte';

	let {
		title,
		items,
		primaryText,
		secondaryText,
		hiddenInputName,
		addLabel,
		onAdd,
		onEdit,
		onRemove
	}: {
		title: string;
		items: T[];
		primaryText: (item: T) => string;
		secondaryText: (item: T) => string;
		hiddenInputName: string;
		addLabel: string;
		onAdd: () => void;
		onEdit: (index: number) => void;
		onRemove: (index: number) => void;
	} = $props();
</script>

<FieldSet {title}>
	{#each items as item, index (index)}
		<div
			class="flex flex-col gap-3 rounded-xl border border-neutral-700 bg-black/45 p-3 sm:flex-row sm:items-stretch sm:justify-between"
		>
			<div class="min-w-0 space-y-2">
				<p class="text-sm font-medium break-all text-neutral-100">
					{primaryText(item)}
				</p>
				<p class="text-sm text-neutral-300">
					{secondaryText(item)}
				</p>
			</div>

			<div
				class="flex items-center justify-between gap-2 sm:flex-col sm:items-end sm:justify-between"
			>
				<button
					type="button"
					onclick={() => onEdit(index)}
					class="flex-1 rounded-lg border border-neutral-700 bg-neutral-900/80 px-3 py-1.5 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800 sm:w-24 sm:flex-none"
				>
					Edit
				</button>
				<button
					type="button"
					onclick={() => onRemove(index)}
					class="flex-1 rounded-lg border border-red-900/80 bg-red-950/40 px-3 py-1.5 text-sm font-medium text-red-200 transition hover:bg-red-900/40 sm:w-24 sm:flex-none"
				>
					Remove
				</button>
			</div>

			<input type="hidden" name={hiddenInputName} value={JSON.stringify(item)} />
		</div>
	{/each}

	<button
		type="button"
		onclick={onAdd}
		class="rounded-lg bg-neutral-200 px-4 py-2 text-sm font-medium text-black transition hover:bg-white"
	>
		{addLabel}
	</button>
</FieldSet>
