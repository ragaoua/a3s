import { getAgentService } from '$lib/server/service/agentService';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const agents = await getAgentService().listAgents();

	return {
		agents
	};
};
