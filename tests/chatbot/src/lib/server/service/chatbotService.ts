import { env } from '$env/dynamic/private';
import type { Message, MessageSendParams, Task } from '@a2a-js/sdk';
import { ClientFactory } from '@a2a-js/sdk/client';
import { v4 as uuidv4 } from 'uuid';

function getMessageResponse(message: Message) {
	return message.parts
		.filter((part) => part.kind === 'text')
		.map((part) => part.text)
		.join('');
}

function getTaskResponse(task: Task) {
	const parts = task.artifacts ? task.artifacts.flatMap((artifact) => artifact.parts) : [];

	if (parts.length === 0) {
		return '<empty response>';
	}

	return parts
		.filter((part) => part.kind === 'text')
		.map((part) => part.text)
		.join('');
}

class ChatbotService {
	private contextId: string | undefined = undefined;

	newChat() {
		this.contextId = undefined;
	}

	async chat(userMessage: string): Promise<string> {
		const port = env.AGENT_PORT ?? '8000';
		const factory = new ClientFactory();
		const client = await factory.createFromUrl(`http://localhost:${port}`);

		const sendParams: MessageSendParams = {
			message: {
				messageId: uuidv4(),
				role: 'user',
				parts: [{ kind: 'text', text: userMessage }],
				kind: 'message',
				contextId: this.contextId
			}
		};

		const result = await client.sendMessage(sendParams);
		this.contextId = result.contextId;

		const response = result.kind === 'task' ? getTaskResponse(result) : getMessageResponse(result);
		return response;
	}
}

export const chatbotService = new ChatbotService();
