import { readFile } from 'node:fs/promises';
import { KubeConfig } from '@kubernetes/client-node';
import { AgentService } from './agentService';

export class InClusterDeploymentAgentService extends AgentService {
	constructor(
		a3sAgentImage: string,
		private readonly agentsNamespace?: string
	) {
		super(a3sAgentImage);
	}

	protected async getNamespace() {
		if (this.agentsNamespace) {
			return this.agentsNamespace;
		}

		const namespaceFile = '/var/run/secrets/kubernetes.io/serviceaccount/namespace';
		try {
			const namespace = (await readFile(namespaceFile, 'utf8')).trim();
			if (namespace) {
				return namespace;
			}
		} catch {
			// Fall through to explicit error with expected sources.
		}

		throw new Error(
			'Missing Kubernetes namespace. Set the agents namespace in the config file or ensure in-cluster namespace file is mounted.'
		);
	}

	protected getKubeConfig() {
		const kc = new KubeConfig();
		kc.loadFromCluster();
		return kc;
	}
}
