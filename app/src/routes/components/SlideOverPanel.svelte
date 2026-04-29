<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		children,
		open,
		title,
		actionLabel,
		actionDisabled = false,
		onClose,
		onAction
	}: {
		children: Snippet<[]>;
		open: boolean;
		title: string;
		actionLabel: string;
		actionDisabled?: boolean;
		onClose: () => void;
		onAction: () => void;
	} = $props();

	function handleSubmit(event: SubmitEvent) {
		event.preventDefault();
		if (!actionDisabled) {
			onAction();
		}
	}
</script>

<div
	inert={!open}
	aria-hidden={!open}
	class={`fixed inset-0 z-40 ${open ? 'pointer-events-auto' : 'pointer-events-none'}`}
>
	<button
		type="button"
		aria-label="Close panel"
		onclick={onClose}
		class={`absolute inset-0 bg-black/60 transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0'}`}
	></button>

	<aside
		aria-label={title}
		class={`absolute inset-y-0 right-0 flex w-full max-w-md flex-col border-l border-neutral-800 bg-neutral-900 p-6 shadow-2xl transition-transform duration-300 ease-in-out ${open ? 'translate-x-0' : 'translate-x-full'}`}
	>
		<form class="flex h-full flex-col gap-6" onsubmit={handleSubmit}>
			<div class="space-y-4">
				<h2 class="text-lg font-semibold text-neutral-100">{title}</h2>
				{@render children()}
			</div>

			<div class="mt-auto flex gap-3">
				<button
					type="button"
					onclick={onClose}
					class="flex-1 rounded-lg border border-neutral-700 bg-black/45 px-4 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800"
				>
					Cancel
				</button>
				<button
					type="submit"
					disabled={actionDisabled}
					class="flex-1 rounded-lg bg-neutral-200 px-4 py-2 text-sm font-medium text-black transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-neutral-200"
				>
					{actionLabel}
				</button>
			</div>
		</form>
	</aside>
</div>
