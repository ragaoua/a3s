import { agentService } from '$lib/server/service/agentService';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const agents = await agentService.listAgents();

	return {
		agents
	};
};
