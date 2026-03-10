import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { containersService } from '$lib/server/service/agentService';

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

		if (authMode !== 'apiKey' && authMode !== 'oauth2') {
			return fail(400, {
				error: 'Authentication mode must be either apiKey or oauth2.'
			});
		}

		let authParams;
		if (authMode === 'oauth2') {
			if (!oauth2IssuerUrl) {
				return fail(400, {
					error: 'OAuth2 issuer URL is required when OAuth2 auth is selected.'
				});
			}
			authParams = { oauth2IssuerUrl, oauth2JwksUrl };
		}

		await containersService.deployAgent({
			model,
			name,
			description,
			instructions,
			apiKey,
			apiUrl,
			mcpServers,
			...authParams
		});

		return {
			success: true
		};
	}
};
