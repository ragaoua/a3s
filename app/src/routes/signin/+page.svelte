<main class="flex min-h-screen items-center justify-center bg-transparent px-4 text-neutral-100">
	<div
		class="w-full max-w-sm rounded-2xl border border-neutral-800 bg-neutral-900/90 p-8 shadow-xl shadow-black/40 backdrop-blur-sm"
	>
		<h1 class="text-2xl font-semibold">Sign in</h1>
		<p class="mt-2 text-sm text-neutral-400">Sign in with your identity provider to continue.</p>
		<form method="POST" class="mt-6">
			<input type="hidden" name="providerId" value="oidc" />
			<input type="hidden" name="redirectTo" value="/" />
			<button
				type="submit"
				class="w-full rounded-lg bg-neutral-200 px-4 py-2 text-sm font-semibold text-black transition hover:bg-white"
			>
				Continue
			</button>
		</form>
	</div>
</main>
