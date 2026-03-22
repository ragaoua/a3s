import { CoreV1Api, KubeConfig, type V1EnvVar } from '@kubernetes/client-node';
import { env } from '$env/dynamic/private';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';

interface DeployAgentParams {
	model: string;
	name: string;
	description: string;
	instructions: string;
	apiKey: string;
	apiUrl: string;
	mcpServers: string[];
	oauth2IssuerUrl?: string;
	oauth2JwksUrl?: string;
}

interface DeployAgentResult {
	agentApiKey?: string;
}

interface KubernetesClusterParams {
	clusterName: string;
	server: string;
	serviceAccount: string;
	serviceAccountToken: string;
	serviceAccountNamespace: string;
	agentsNamespace: string;
	caData: string;
}

abstract class AgentService {
	abstract deployToKubernetes(params: DeployAgentParams): Promise<DeployAgentResult>;

	protected async runPod(kc: KubeConfig, namespace: string, agentParams: DeployAgentParams) {
		const core = kc.makeApiClient(CoreV1Api);

		const mcpServersValue = agentParams.mcpServers.join(',');

		const authVars: V1EnvVar[] = [];
		let agentApiKey: string | undefined;
		if (agentParams.oauth2IssuerUrl) {
			authVars.push({ name: 'OAUTH2_ISSUER_URL', value: agentParams.oauth2IssuerUrl });
			if (agentParams.oauth2JwksUrl) {
				authVars.push({ name: 'OAUTH2_JWKS_URL', value: agentParams.oauth2JwksUrl });
			}
			console.log('Agent will be configured with OAuth2 Authorization.');
		} else {
			agentApiKey = randomBytes(32).toString('hex');
			authVars.push({ name: 'AGENT_API_KEY', value: agentApiKey });
			console.log(
				`Agent will be configured with API Key Authorization.\nUse API Key ${agentApiKey}`
			);
		}

		const listenPort = 10000;
		const pod = await core.createNamespacedPod({
			namespace,
			body: {
				apiVersion: 'v1',
				kind: 'Pod',
				metadata: {
					generateName: agentParams.name.toLowerCase()
				},
				spec: {
					restartPolicy: 'Never',
					containers: [
						{
							name: agentParams.name.toLowerCase(),
							image: 'localhost/a3s-agent',
							imagePullPolicy: 'Never',
							env: [
								{ name: 'MODEL', value: agentParams.model },
								{ name: 'AGENT_NAME', value: agentParams.name },
								{ name: 'AGENT_INSTRUCTIONS', value: agentParams.instructions },
								{ name: 'AGENT_DESCRIPTION', value: agentParams.description },
								{ name: 'LLM_API_KEY', value: agentParams.apiKey },
								{ name: 'LLM_API_URI', value: agentParams.apiUrl },
								{ name: 'LISTEN_PORT', value: String(listenPort) },
								{ name: 'MCP_SERVERS', value: mcpServersValue },
								...authVars
							],
							stdin: true,
							tty: true,
							ports: [{ containerPort: listenPort }]
						}
					]
				}
			}
		});

		console.log(
			`Started Kubernetes agent pod ${pod.metadata?.name ?? '<pending-name>'} in namespace ${namespace}.`
		);

		return { agentApiKey };
	}
}

class RemoteDeploymentAgentService extends AgentService {
	constructor(private readonly kubernetesParams: KubernetesClusterParams) {
		super();
	}

	async deployToKubernetes(agentParams: DeployAgentParams) {
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

		const namespace = this.kubernetesParams.agentsNamespace;

		return super.runPod(kc, namespace, agentParams);
	}
}

class InClusterDeploymentAgentService extends AgentService {
	private async getNamespace(): Promise<string> {
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

	async deployToKubernetes(params: DeployAgentParams) {
		const kc = new KubeConfig();
		kc.loadFromCluster();

		const namespace = await this.getNamespace();

		return super.runPod(kc, namespace, params);
	}
}

function getRequiredEnv(name: string): string {
	const value = env[name];

	if (!value) {
		throw new Error(`Missing required environment variable: ${name}`);
	}

	return value;
}

type K8sDeployMode = 'inCluster' | 'external' | 'auto';

function resolveDeployMode(): 'inCluster' | 'external' {
	const raw = (env.K8S_DEPLOY_MODE ?? 'auto') as K8sDeployMode;
	if (raw === 'inCluster' || raw === 'external') return raw;
	if (raw === 'auto') {
		return env.KUBERNETES_SERVICE_HOST ? 'inCluster' : 'external';
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
