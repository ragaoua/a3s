import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { getAgentService } from '$lib/server/service/agentService';
import { agentConfigFormSchema } from '../lib/types/agentConfigForm';

function trimOrUndefined(formData: FormData, name: string): string | undefined {
	const value = String(formData.get(name) ?? '').trim();
	return value === '' ? undefined : value;
}

function parseRepeatedJsonField(formData: FormData, name: string) {
	return formData.getAll(name).map((value) => {
		return JSON.parse(String(value));
	});
}

function parseJsonField(formData: FormData, name: string): unknown {
	const value = formData.get(name);
	if (typeof value !== 'string' || value === '') {
		return undefined;
	}
	return JSON.parse(value);
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
			oauth2Policies: parseJsonField(formData, 'oauth2Policies'),
			mcpServers: parseRepeatedJsonField(formData, 'mcpServers'),
			subagents: parseRepeatedJsonField(formData, 'subagents'),
			skills: parseRepeatedJsonField(formData, 'skills')
		};

		const formDataValidationResult = agentConfigFormSchema.safeParse(formDataDict);

		if (!formDataValidationResult.success) {
			return fail(400, {
				error: `Invalid config: ${formDataValidationResult.error.message}`
			});
		}

		const data = formDataValidationResult.data;
		const { agentApiKey } = await getAgentService().deployToKubernetes(data);

		return {
			success: true,
			agentApiKey
		};
	}
};
