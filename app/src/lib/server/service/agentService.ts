import { CoreV1Api, KubeConfig, type V1EnvVar } from '@kubernetes/client-node';
import { env } from '$env/dynamic/private';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import type { Auth } from '$lib/types/auth';

interface DeployAgentParams {
	model: string;
	name: string;
	description: string;
	instructions: string;
	apiKey: string;
	apiUrl: string;
	mcpServers: string[];
	auth: Auth;
}

interface DeployAgentResult {
	agentApiKey?: string;
}

export interface AgentSummary {
	agentName: string;
	podName: string;
	status: string;
	createdAt: string;
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
	protected abstract getKubeConfig(): KubeConfig;

	protected abstract getNamespace(): Promise<string>;

	private pushIfValue(vars: V1EnvVar[], name: string, value?: string) {
		if (value) {
			vars.push({ name, value });
		}
	}

	async deployToKubernetes(agentParams: DeployAgentParams): Promise<DeployAgentResult> {
		const kc = this.getKubeConfig();
		const namespace = await this.getNamespace();
		const core = kc.makeApiClient(CoreV1Api);

		const mcpServersValue = agentParams.mcpServers.join(',');

		const authVars: V1EnvVar[] = [];
		let agentApiKey: string | undefined;
		if (agentParams.auth.type === 'none') {
			authVars.push({ name: 'NO_AUTH', value: '1' });
			console.log('Agent will be configured with no authentication.');
		} else if (agentParams.auth.type === 'oauth2') {
			authVars.push({ name: 'OAUTH2_ISSUER_URL', value: agentParams.auth.oauth2IssuerUrl });
			this.pushIfValue(authVars, 'OAUTH2_JWKS_URL', agentParams.auth.oauth2JwksUrl);
			this.pushIfValue(authVars, 'OAUTH2_AUDIENCE', agentParams.auth.oauth2Audience);
			console.log('Agent will be configured with OAuth2 Authorization.');
		} else {
			agentApiKey = randomBytes(32).toString('hex');
			authVars.push({ name: 'AGENT_API_KEY', value: agentApiKey });
			console.log(
				`Agent will be configured with API Key Authorization.\nUse API Key ${agentApiKey}`
			);
		}

		const listenPort = 8000;
		const listenAddress = '0.0.0.0';
		const pod = await core.createNamespacedPod({
			namespace,
			body: {
				apiVersion: 'v1',
				kind: 'Pod',
				metadata: {
					generateName: agentParams.name.toLowerCase(),
					// NOTE: these can then be used as selectors to create a service
					// that will make the agent available from the outside.
					// Problem is, the agent's name is nowhere constraint to be unique,
					// which means that multiple pods can share the same labels and
					// be matched by the same ClusterIP, NodePort or whatever.
					// Something to think about later
					labels: {
						run: 'agent',
						name: agentParams.name
					}
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
								{ name: 'LISTEN_ADDRESS', value: listenAddress },
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

	async listAgents(): Promise<AgentSummary[]> {
		const kc = this.getKubeConfig();
		const core = kc.makeApiClient(CoreV1Api);

		const namespace = await this.getNamespace();
		const podList = await core.listNamespacedPod({
			namespace,
			labelSelector: 'run=agent'
		});

		return podList.items
			.map((pod) => {
				const createdAt = pod.metadata?.creationTimestamp;

				return {
					podName: pod.metadata?.name ?? '<unknown-pod>',
					agentName: pod.metadata?.labels?.name ?? pod.metadata?.name ?? '<unknown-agent>',
					status: pod.status?.phase ?? 'Unknown',
					createdAt: createdAt ? new Date(createdAt).toISOString() : ''
				} satisfies AgentSummary;
			})
			.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
	}
}

class RemoteDeploymentAgentService extends AgentService {
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

class InClusterDeploymentAgentService extends AgentService {
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

function getRequiredEnv(name: string): string {
	const value = env[name];

	if (!value) {
		throw new Error(`Missing required environment variable: ${name}`);
	}

	return value;
}

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
