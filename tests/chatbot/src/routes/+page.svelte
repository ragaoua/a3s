<script lang="ts">
	import { enhance } from '$app/forms';
	import type { Message } from '$lib/types/message.js';

	const { form } = $props();
	let messages = $state<Message[]>([]);
	let messageInput = $state('');
	let isSubmitting = $state(false);
	$effect(() => {
		if (form?.success && form.messages) {
			messages = form.messages
		}
	});
</script>

<div class="mx-auto flex h-screen max-w-3xl flex-col p-4">
	<h1 class="mb-4 text-2xl font-bold">Chatbot</h1>

	<!-- Chat History -->
	<div
		class="mb-4 flex-1 space-y-3 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-4"
	>
		{#if messages.length === 0}
			<p class="text-gray-400">Start a conversation...</p>
		{:else}
			{#each messages as message (message)}
				<div class="flex {message.role === 'user' ? 'justify-end' : 'justify-start'}">
					<div
						class="max-w-[80%] rounded-lg px-4 py-2 {message.role === 'user'
							? 'bg-blue-500 text-white'
							: 'bg-white text-gray-800'}"
					>
						{message.content}
					</div>
				</div>
			{/each}
		{/if}
	</div>

	<!-- Message Input Form -->
	<form
		method="POST"
		action="?/sendMessage"
		use:enhance={() => {
      messages.push({
        role: "user", content: messageInput
      });
			isSubmitting = true;
			return async ({ update }) => {
				await update();
				messageInput = '';
				isSubmitting = false;
			};
		}}
		class="flex gap-2"
	>
		<input type="hidden" name="chatHistory" value={JSON.stringify(messages)} />
		<input
			type="text"
			name="message"
			bind:value={messageInput}
			placeholder="Type your message..."
			disabled={isSubmitting}
			autofocus
			class="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none disabled:bg-gray-100"
		/>
		<button
			type="submit"
			disabled={isSubmitting || messageInput.trim() === ''}
			class="rounded-lg bg-blue-500 px-6 py-2 text-white hover:bg-blue-600 disabled:bg-gray-300"
		>
			{isSubmitting ? 'Sending...' : 'Send'}
		</button>
	</form>

	{#if form?.error}
		<p class="mt-2 text-sm text-red-500">{form.error}</p>
	{/if}
</div>
