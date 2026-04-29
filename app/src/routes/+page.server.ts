import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { agentService } from '$lib/server/service/agentService';
import { agentConfigFormSchema } from '../lib/types/agentConfigForm';

function trimOrUndefined(formData: FormData, name: string): string | undefined {
	const value = String(formData.get(name) ?? '').trim();
	return value === '' ? undefined : value;
}

export const actions: Actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const formDataDict = {
			model: trimOrUndefined(formData, 'model'),
			apiUrl: trimOrUndefined(formData, 'apiUrl'),
			apiKey: trimOrUndefined(formData, 'apiKey'),
			name: trimOrUndefined(formData, 'name'),
			description: trimOrUndefined(formData, 'description'),
			instructions: trimOrUndefined(formData, 'instructions'),
			authMode: trimOrUndefined(formData, 'authMode'),
			oauth2IssuerUrl: trimOrUndefined(formData, 'oauth2IssuerUrl'),
			mcpServers: formData.getAll('mcpServers').map((value) => {
				try {
					return JSON.parse(String(value));
				} catch {
					return value;
				}
			}),
			subagents: formData.getAll('subagents').map((value) => {
				try {
					return JSON.parse(String(value));
				} catch {
					return value;
				}
			}),
			skills: formData.getAll('skills').map((value) => {
				try {
					return JSON.parse(String(value));
				} catch {
					return value;
				}
			})
		};

		const formDataValidationResult = agentConfigFormSchema.safeParse(formDataDict);

		if (!formDataValidationResult.success) {
			return fail(400, {
				error: `Invalid config: ${formDataValidationResult.error.message}`
			});
		}

		const data = formDataValidationResult.data;
		const { agentApiKey } = await agentService.deployToKubernetes(data);

		return {
			success: true,
			agentApiKey
		};
	}
};
