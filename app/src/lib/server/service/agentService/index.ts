import { getConfig } from '$lib/server/config';
import type { AgentService } from './agentService';
import { InClusterDeploymentAgentService } from './inClusterDeploymentAgentService';
import { RemoteDeploymentAgentService } from './remoteDeploymentAgentService';

let cachedAgentService: AgentService | undefined;

export function getAgentService(): AgentService {
	if (!cachedAgentService) {
		const config = getConfig();
		cachedAgentService =
			config.deployment.mode === 'inCluster'
				? new InClusterDeploymentAgentService(config.agentImage, config.deployment.agentsNamespace)
				: new RemoteDeploymentAgentService(config.agentImage, config.deployment);
	}
	return cachedAgentService;
}
