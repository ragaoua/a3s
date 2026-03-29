import { CoreV1Api, KubeConfig } from '@kubernetes/client-node';
import { env } from '$env/dynamic/private';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import YAML from 'yaml';
import type { AgentRuntimeConfig } from '../../types/agentRuntimeConfig';
import type { AgentConfigForm } from '$lib/types/agentConfigForm';

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

	async deployToKubernetes(agentConfig: AgentConfigForm): Promise<DeployAgentResult> {
		const kc = this.getKubeConfig();
		const namespace = await this.getNamespace();
		const core = kc.makeApiClient(CoreV1Api);

		const agentRuntimeConfig = this.buildAgentRuntimeConfig(agentConfig);

		if (agentRuntimeConfig.auth === 'none') {
			console.log('Agent will be configured with no authentication.');
		} else if (agentRuntimeConfig.auth.mode === 'oauth2') {
			console.log('Agent will be configured with OAuth2 Authorization.');
		} else {
			console.log(
				`Agent will be configured with API Key Authorization.\nUse API Key ${agentRuntimeConfig.auth.api_key}`
			);
		}

		const configSecretName = `a3s-agent-config-${randomBytes(8).toString('hex')}`;
		await core.createNamespacedSecret({
			namespace,
			body: {
				apiVersion: 'v1',
				kind: 'Secret',
				metadata: {
					name: configSecretName,
					labels: {
						run: 'agent'
					}
				},
				type: 'Opaque',
				stringData: {
					'agent.yaml': YAML.stringify(agentRuntimeConfig)
				}
			}
		});

		try {
			const pod = await core.createNamespacedPod({
				namespace,
				body: {
					apiVersion: 'v1',
					kind: 'Pod',
					metadata: {
						generateName: agentRuntimeConfig.agent.name.toLowerCase(),
						// NOTE: these can then be used as selectors to create a service
						// that will make the agent available from the outside.
						// Problem is, the agent's name is nowhere constrained to be unique,
						// which means that multiple pods can share the same labels and
						// be matched by the same ClusterIP, NodePort or whatever.
						// Something to think about later
						labels: {
							run: 'agent',
							name: agentRuntimeConfig.agent.name
						}
					},
					spec: {
						restartPolicy: 'Never',
						containers: [
							{
								name: agentRuntimeConfig.agent.name.toLowerCase(),
								image: 'localhost/a3s-agent',
								imagePullPolicy: 'Never',
								stdin: true,
								tty: true,
								ports: [{ containerPort: agentRuntimeConfig.server.listen_port }],
								volumeMounts: [
									{
										name: 'agent-config',
										mountPath: '/app/config',
										readOnly: true
									}
								]
							}
						],
						volumes: [
							{
								name: 'agent-config',
								secret: {
									secretName: configSecretName,
									items: [{ key: 'agent.yaml', path: 'agent.yaml' }]
								}
							}
						]
					}
				}
			});

			console.log(
				`Started Kubernetes agent pod ${pod.metadata?.name ?? '<pending-name>'} in namespace ${namespace}.`
			);

			if (agentRuntimeConfig.auth !== 'none' && agentRuntimeConfig.auth.mode === 'api_key') {
				return { agentApiKey: agentRuntimeConfig.auth.api_key };
			} else {
				return {};
			}
		} catch (error) {
			try {
				await core.deleteNamespacedSecret({
					name: configSecretName,
					namespace
				});
			} catch (cleanupError) {
				console.warn(`Failed to clean up agent config secret ${configSecretName}:`, cleanupError);
			}

			throw error;
		}
	}

	private buildAgentRuntimeConfig(agentConfig: AgentConfigForm): AgentRuntimeConfig {
		return {
			llm: {
				api_url: agentConfig.apiUrl,
				api_key: agentConfig.apiKey,
				model: agentConfig.model
			},
			agent: {
				name: agentConfig.name,
				description: agentConfig.description,
				instructions: agentConfig.instructions
			},
			server: {
				listen_address: '0.0.0.0',
				listen_port: 8000
			},
			auth:
				agentConfig.authMode === 'none'
					? 'none'
					: agentConfig.authMode === 'oauth2'
						? {
								mode: 'oauth2',
								issuer_url: agentConfig.oauth2IssuerUrl,
								jwks_url: agentConfig.oauth2JwksUrl,
								audience: agentConfig.oauth2Audience
							}
						: {
								mode: 'api_key',
								api_key: randomBytes(32).toString('hex')
							},
			mcp_servers: agentConfig.mcpServers
		};
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
