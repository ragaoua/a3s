import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { containersService } from '$lib/server/service/agentService';

export const actions: Actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const name = String(formData.get('name') ?? '').trim();
		const description = String(formData.get('description') ?? '').trim();
		const instructions = String(formData.get('instructions') ?? '').trim();
		const apiKey = String(formData.get('apiKey') ?? '').trim();
		const apiUrl = String(formData.get('apiUrl') ?? '').trim();
		// const mcpServers = formData
		// 	.getAll('mcpServers')
		// 	.map((value) => String(value).trim())
		// 	.filter((value) => value.length > 0);

		if (!name || !description || !instructions || !apiKey || !apiUrl) {
			return fail(400, {
				error: 'Name, description, instructions, API key, and API URL are required.'
			});
		}

		await containersService.deployAgent({
			name,
			description,
			instructions,
			apiKey,
			apiUrl
			// mcpServers
		});

		return {
			success: true
		};
	}
};
