<script lang="ts">
	import { page } from '$app/state';
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { resolve } from '$app/paths';

	let { children, data } = $props();

	const isActive = (path: string) => page.url.pathname === path;
	const isAuthRoute = $derived(['/signin', '/signout'].includes(page.url.pathname));
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
{#if isAuthRoute}
	{@render children()}
{:else}
	<aside
		class="fixed inset-y-0 left-0 flex w-64 flex-col border-r border-neutral-800 bg-neutral-950/90 p-4 backdrop-blur-sm"
	>
		<nav class="flex flex-1 flex-col gap-2">
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

		{#if data.session?.user}
			<div class="mt-2 border-t border-neutral-800 pt-3">
				<p class="px-3 text-xs text-neutral-400">Signed in as</p>
				<p class="truncate px-3 pb-2 text-sm text-neutral-200">
					{data.session.user.email ?? data.session.user.name ?? 'user'}
				</p>
				<form method="POST" action={resolve('/signout')}>
					<button
						type="submit"
						class="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-neutral-300 transition hover:bg-neutral-800 hover:text-neutral-100"
					>
						Sign out
					</button>
				</form>
			</div>
		{/if}
	</aside>

	<div class="pl-64">{@render children()}</div>
{/if}
