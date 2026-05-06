import { fail } from '@sveltejs/kit';
import { getAgentService } from '$lib/server/service/agentService';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const agents = await getAgentService().listAgents();

	return {
		agents
	};
};

export const actions: Actions = {
	delete: async ({ request }) => {
		const formData = await request.formData();
		const deploymentName = String(formData.get('deploymentName') ?? '').trim();

		if (!deploymentName) {
			return fail(400, { error: 'Missing deployment name.' });
		}

		try {
			await getAgentService().deleteAgent(deploymentName);
		} catch (error) {
			return fail(500, {
				error: `Failed to delete agent: ${error instanceof Error ? error.message : String(error)}`
			});
		}

		return { success: true };
	}
};
