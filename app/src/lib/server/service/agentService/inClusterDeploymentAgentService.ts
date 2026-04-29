import { env } from '$env/dynamic/private';
import { readFile } from 'node:fs/promises';
import { KubeConfig } from '@kubernetes/client-node';
import { AgentService } from './agentService';

export class InClusterDeploymentAgentService extends AgentService {
	protected async getNamespace() {
		const namespaceFromEnv = env.K8S_AGENTS_NAMESPACE;
		if (namespaceFromEnv) {
			return namespaceFromEnv;
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
			'Missing Kubernetes namespace. Set K8S_AGENTS_NAMESPACE or ensure in-cluster namespace file is mounted.'
		);
	}

	protected getKubeConfig() {
		const kc = new KubeConfig();
		kc.loadFromCluster();
		return kc;
	}
}
