import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { agentService } from '$lib/server/service/agentService';
import type { Auth } from '$lib/types/auth';

export const actions: Actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const model = String(formData.get('model') ?? '').trim();
		const name = String(formData.get('name') ?? '').trim();
		const description = String(formData.get('description') ?? '').trim();
		const instructions = String(formData.get('instructions') ?? '').trim();
		const authMode = String(formData.get('authMode') ?? 'apiKey').trim();
		const apiKey = String(formData.get('apiKey') ?? '').trim();
		const oauth2IssuerUrl = String(formData.get('oauth2IssuerUrl') ?? '').trim();
		const oauth2JwksUrl = String(formData.get('oauth2JwksUrl') ?? '').trim();
		const apiUrl = String(formData.get('apiUrl') ?? '').trim();
		const mcpServers = formData
			.getAll('mcpServers')
			.map((value) => String(value).trim())
			.filter((value) => value.length > 0);

		if (!name || !description || !instructions || !apiKey || !apiUrl) {
			return fail(400, {
				error: 'Name, description, instructions, API key, and API URL are required.'
			});
		}

		if (authMode !== 'apiKey' && authMode !== 'oauth2' && authMode !== 'none') {
			return fail(400, {
				error: 'Authentication mode must be one of apiKey, oauth2, or none.'
			});
		}

		let auth: Auth;
		if (authMode === 'oauth2') {
			if (!oauth2IssuerUrl) {
				return fail(400, {
					error: 'OAuth2 issuer URL is required when OAuth2 auth is selected.'
				});
			}
			auth = { type: 'oauth2', oauth2IssuerUrl, oauth2JwksUrl };
		} else if (authMode === 'apiKey') {
			auth = { type: 'apiKey' };
		} else {
			auth = { type: 'none' };
		}

		const { agentApiKey } = await agentService.deployToKubernetes({
			model,
			name,
			description,
			instructions,
			apiKey,
			apiUrl,
			mcpServers,
			auth
		});

		return {
			success: true,
			agentApiKey
		};
	}
};
