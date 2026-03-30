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
			name: trimOrUndefined(formData, 'name'),
			description: trimOrUndefined(formData, 'description'),
			instructions: trimOrUndefined(formData, 'instructions'),
			authMode: trimOrUndefined(formData, 'authMode'),
			apiKey: trimOrUndefined(formData, 'apiKey'),
			oauth2IssuerUrl: trimOrUndefined(formData, 'oauth2IssuerUrl'),
			oauth2JwksUrl: trimOrUndefined(formData, 'oauth2JwksUrl'),
			oauth2Rfc9068Enabled: formData.has('oauth2Rfc9068Enabled'),
			oauth2ResourceServer: trimOrUndefined(formData, 'oauth2ResourceServer'),
			apiUrl: trimOrUndefined(formData, 'apiUrl'),
			mcpServers: formData
				.getAll('mcpServers')
				.map((value) => String(value).trim())
				.filter((value) => value.length > 0)
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
