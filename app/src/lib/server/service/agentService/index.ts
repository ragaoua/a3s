import { env } from '$env/dynamic/private';
import { getRequiredEnv } from '$lib/server/utils';
import type { AgentService } from './agentService';
import { InClusterDeploymentAgentService } from './inClusterDeploymentAgentService';
import { RemoteDeploymentAgentService } from './remoteDeploymentAgentService';

type K8sDeployMode = 'inCluster' | 'remote' | 'auto';

function resolveDeployMode(): 'inCluster' | 'remote' {
	const raw = (env.K8S_DEPLOY_MODE ?? 'auto') as K8sDeployMode;
	if (raw === 'inCluster' || raw === 'remote') return raw;
	if (raw === 'auto') {
		return env.KUBERNETES_SERVICE_HOST ? 'inCluster' : 'remote';
	}
	throw new Error(`Invalid K8S_DEPLOY_MODE: ${raw}`);
}

export const agentService: AgentService =
	resolveDeployMode() === 'inCluster'
		? new InClusterDeploymentAgentService()
		: new RemoteDeploymentAgentService({
				clusterName: getRequiredEnv('K8S_CLUSTER_NAME'),
				server: getRequiredEnv('K8S_SERVER_URL'),
				serviceAccount: getRequiredEnv('K8S_SERVICE_ACCOUNT'),
				serviceAccountToken: getRequiredEnv('K8S_SERVICE_ACCOUNT_TOKEN'),
				serviceAccountNamespace: getRequiredEnv('K8S_SERVICE_ACCOUNT_NAMESPACE'),
				agentsNamespace: getRequiredEnv('K8S_AGENTS_NAMESPACE'),
				caData: getRequiredEnv('K8S_CA_DATA')
			});
