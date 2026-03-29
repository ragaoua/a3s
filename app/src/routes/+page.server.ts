import { fail } from '@sveltejs/kit';
import type { Actions } from './$types';
import { agentService } from '$lib/server/service/agentService';
import { agentConfigFormSchema } from '../lib/types/agentConfigForm';

function getTrimmedStringOrNull(formData: FormData, name: string): string | null {
	const rawValue = formData.get(name);

	if (rawValue === null) return null;

	return String(rawValue).trim();
}

export const actions: Actions = {
	default: async ({ request }) => {
		const formData = await request.formData();
		const formDataDict = {
			model: getTrimmedStringOrNull(formData, 'model'),
			name: getTrimmedStringOrNull(formData, 'name'),
			description: getTrimmedStringOrNull(formData, 'description'),
			instructions: getTrimmedStringOrNull(formData, 'instructions'),
			authMode: getTrimmedStringOrNull(formData, 'authMode'),
			apiKey: getTrimmedStringOrNull(formData, 'apiKey'),
			oauth2IssuerUrl: getTrimmedStringOrNull(formData, 'oauth2IssuerUrl'),
			oauth2Audience: getTrimmedStringOrNull(formData, 'oauth2Audience'),
			oauth2JwksUrl: getTrimmedStringOrNull(formData, 'oauth2JwksUrl'),
			apiUrl: getTrimmedStringOrNull(formData, 'apiUrl'),
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
