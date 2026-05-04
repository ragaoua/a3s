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
		const podName = String(formData.get('podName') ?? '').trim();

		if (!podName) {
			return fail(400, { error: 'Missing pod name.' });
		}

		try {
			await getAgentService().deleteAgent(podName);
		} catch (error) {
			return fail(500, {
				error: `Failed to delete agent: ${error instanceof Error ? error.message : String(error)}`
			});
		}

		return { success: true };
	}
};
