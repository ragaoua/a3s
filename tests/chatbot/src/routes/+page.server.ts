import { fail, type Actions, type Load } from '@sveltejs/kit';
import { chatbotService, DEFAULT_AGENT_URL } from '$lib/server/service/chatbotService';
import type { Message } from '$lib/types/message';

export const load: Load = () => {
	return {
		defaultAgentUrl: DEFAULT_AGENT_URL
	};
};

export const actions = {
	sendMessage: async ({ request }) => {
		const data = await request.formData();
		const message = data.get('message')?.toString();
		const chatHistoryJson = data.get('chatHistory')?.toString();
		const agentUrl = data.get('agentUrl')?.toString().trim();

		if (!message || message.trim() === '') {
			return fail(400, { error: 'Message cannot be empty' });
		}

		if (!agentUrl) {
			return fail(400, { error: 'Agent URL cannot be empty' });
		}

		try {
			const chatHistory: Message[] = chatHistoryJson ? JSON.parse(chatHistoryJson) : [];
			if (chatHistory.length === 0) {
				// Reset the contextId whenever we start a new conversation.
				chatbotService.newChat();
			}

			const assistantMessage = await chatbotService.chat(message, agentUrl);

			chatHistory.push(
				...([
					{
						role: 'user',
						content: message
					},
					{
						role: 'assistant',
						content: assistantMessage
					}
				] satisfies Message[])
			);

			return {
				success: true,
				messages: chatHistory
			};
		} catch (error) {
			console.error('Error generating response:', error);
			return fail(500, { error: 'Failed to generate response' });
		}
	}
} satisfies Actions;
