import { Role, type Message, type SendMessageRequest, type Task } from '@a2a-js/sdk';
import { ClientFactory } from '@a2a-js/sdk/client';
import { v4 as uuidv4 } from 'uuid';

export const DEFAULT_AGENT_URL = 'http://localhost:8000';

function getMessageResponse(message: Message) {
	return message.parts
		.filter((part) => part.content?.$case === 'text')
		.map((part) => part.content?.value ?? '')
		.join('');
}

function getTaskResponse(task: Task) {
	const parts = task.artifacts ? task.artifacts.flatMap((artifact) => artifact.parts) : [];

	if (parts.length === 0) {
		return '<empty response>';
	}

	return parts
		.filter((part) => part.content?.$case === 'text')
		.map((part) => part.content?.value ?? '')
		.join('');
}

class ChatbotService {
	private contextId: string | undefined = undefined;

	newChat() {
		this.contextId = undefined;
	}

	async chat(userMessage: string, agentUrl: string): Promise<string> {
		const factory = new ClientFactory();
		const client = await factory.createFromUrl(agentUrl);

		const sendRequest: SendMessageRequest = {
			tenant: '',
			message: {
				messageId: uuidv4(),
				role: Role.ROLE_USER,
				parts: [
					{
						content: { $case: 'text', value: userMessage },
						metadata: undefined,
						filename: '',
						mediaType: 'text/plain'
					}
				],
				taskId: '',
				contextId: this.contextId ?? '',
				extensions: [],
				metadata: {},
				referenceTaskIds: []
			},
			configuration: undefined,
			metadata: {}
		};

		const result = await client.sendMessage(sendRequest);
		this.contextId = result.contextId;

		const response = 'id' in result ? getTaskResponse(result) : getMessageResponse(result);
		return response;
	}
}

export const chatbotService = new ChatbotService();
