<script lang="ts">
	import { page } from '$app/state';
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { resolve } from '$app/paths';

	let { children } = $props();

	const isActive = (path: string) => page.url.pathname === path;
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<aside
	class="fixed inset-y-0 left-0 w-64 border-r border-neutral-800 bg-neutral-950/90 p-4 backdrop-blur-sm"
>
	<nav class="flex h-full flex-col gap-2">
		<a
			href={resolve('/')}
			class={`rounded-lg px-3 py-2 text-sm font-medium transition ${
				isActive('/')
					? 'bg-neutral-100 text-black'
					: 'text-neutral-300 hover:bg-neutral-800 hover:text-neutral-100'
			}`}
		>
			Create Agent
		</a>
		<a
			href={resolve('/agents')}
			class={`rounded-lg px-3 py-2 text-sm font-medium transition ${
				isActive('/agents')
					? 'bg-neutral-100 text-black'
					: 'text-neutral-300 hover:bg-neutral-800 hover:text-neutral-100'
			}`}
		>
			Agents
		</a>
	</nav>
</aside>

<div class="pl-64">{@render children()}</div>
