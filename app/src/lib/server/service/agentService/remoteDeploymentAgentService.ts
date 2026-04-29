import { KubeConfig } from '@kubernetes/client-node';
import type { KubernetesClusterParams } from './types/kubernetesClusterParams';
import { AgentService } from './agentService';

export class RemoteDeploymentAgentService extends AgentService {
	constructor(private readonly kubernetesParams: KubernetesClusterParams) {
		super();
	}

	protected async getNamespace() {
		return this.kubernetesParams.agentsNamespace;
	}

	protected getKubeConfig() {
		const kc = new KubeConfig();
		kc.loadFromOptions({
			clusters: [
				{
					name: this.kubernetesParams.clusterName,
					server: this.kubernetesParams.server,
					caData: this.kubernetesParams.caData
				}
			],
			users: [
				{
					name: this.kubernetesParams.serviceAccount,
					token: this.kubernetesParams.serviceAccountToken,
					namespace: this.kubernetesParams.serviceAccountNamespace
				}
			],
			contexts: [
				{
					cluster: this.kubernetesParams.clusterName,
					user: this.kubernetesParams.serviceAccount,
					namespace: this.kubernetesParams.serviceAccountNamespace
				}
			]
		});

		return kc;
	}
}
