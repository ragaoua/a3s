import { CoreV1Api, KubeConfig } from '@kubernetes/client-node';
import { env } from '$env/dynamic/private';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import YAML from 'yaml';
import { agentRuntimeConfigSchema, type AgentRuntimeConfig } from '../../types/agentRuntimeConfig';
import type { AgentConfigForm } from '$lib/types/agentConfigForm';
import { AGENT_NAME_ANNOTATION, sanitizeKubernetesName } from './kubernetesName';

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

interface AgentDeploymentConfig {
	runtimeConfig: AgentRuntimeConfig;
	secretData: Record<string, string>;
}

const AGENT_API_KEY_ENV_VAR = 'A3S_AGENT_API_KEY';

abstract class AgentService {
	protected abstract getKubeConfig(): KubeConfig;

	protected abstract getNamespace(): Promise<string>;

	async deployToKubernetes(agentConfig: AgentConfigForm): Promise<DeployAgentResult> {
		const kc = this.getKubeConfig();
		const namespace = await this.getNamespace();
		const core = kc.makeApiClient(CoreV1Api);

		const { runtimeConfig, secretData } = this.buildAgentDeploymentConfig(agentConfig);
		const kubernetesAgentName = sanitizeKubernetesName(runtimeConfig.agent.name);

		if (runtimeConfig.auth === 'none') {
			console.log('Agent will be configured with no authentication.');
		} else if (runtimeConfig.auth.mode === 'oauth2') {
			console.log('Agent will be configured with OAuth2 Authorization.');
		} else {
			console.log(
				`Agent will be configured with API Key Authorization.\nUse API Key ${runtimeConfig.auth.api_key}`
			);
		}

		const resourceSuffix = randomBytes(8).toString('hex');
		const configMapName = `a3s-${kubernetesAgentName}-config-${resourceSuffix}`;
		const secretName = `a3s-${kubernetesAgentName}-secret-${resourceSuffix}`;
		let configMapCreated = false;
		let secretCreated = false;

		try {
			await core.createNamespacedConfigMap({
				namespace,
				body: {
					apiVersion: 'v1',
					kind: 'ConfigMap',
					metadata: {
						name: configMapName,
						labels: {
							run: 'agent'
						}
					},
					data: {
						'agent.yaml': YAML.stringify(runtimeConfig)
					}
				}
			});
			configMapCreated = true;

			await core.createNamespacedSecret({
				namespace,
				body: {
					apiVersion: 'v1',
					kind: 'Secret',
					metadata: {
						name: secretName,
						labels: {
							run: 'agent'
						}
					},
					type: 'Opaque',
					stringData: secretData
				}
			});
			secretCreated = true;

			const pod = await core.createNamespacedPod({
				namespace,
				body: {
					apiVersion: 'v1',
					kind: 'Pod',
					metadata: {
						generateName: `${kubernetesAgentName}-`,
						annotations: {
							[AGENT_NAME_ANNOTATION]: runtimeConfig.agent.name
						},
						// NOTE: these can then be used as selectors to create a service
						// that will make the agent available from the outside.
						// Problem is, the agent's name is nowhere constrained to be unique,
						// which means that multiple pods can share the same labels and
						// be matched by the same ClusterIP, NodePort or whatever.
						// Something to think about later
						labels: {
							run: 'agent',
							name: kubernetesAgentName
						}
					},
					spec: {
						restartPolicy: 'Never',
						containers: [
							{
								name: kubernetesAgentName,
								image: 'localhost/a3s-agent',
								imagePullPolicy: 'Never',
								stdin: true,
								tty: true,
								ports: [{ containerPort: runtimeConfig.server.listen_port }],
								env: Object.keys(secretData).map((envVarName) => ({
									name: envVarName,
									valueFrom: {
										secretKeyRef: {
											name: secretName,
											key: envVarName
										}
									}
								})),
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
								configMap: {
									name: configMapName,
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
		} catch (error) {
			if (secretCreated) {
				try {
					await core.deleteNamespacedSecret({
						name: secretName,
						namespace
					});
				} catch (cleanupError) {
					console.warn(`Failed to clean up agent secret ${secretName}:`, cleanupError);
				}
			}

			if (configMapCreated) {
				try {
					await core.deleteNamespacedConfigMap({
						name: configMapName,
						namespace
					});
				} catch (cleanupError) {
					console.warn(`Failed to clean up agent config map ${configMapName}:`, cleanupError);
				}
			}

			throw error;
		}

		if (AGENT_API_KEY_ENV_VAR in secretData) {
			return { agentApiKey: secretData[AGENT_API_KEY_ENV_VAR] };
		} else {
			return {};
		}
	}

	private buildAgentDeploymentConfig(agentConfig: AgentConfigForm): AgentDeploymentConfig {
		const agentApiKey =
			agentConfig.authMode === 'apiKey' ? randomBytes(32).toString('hex') : undefined;
		const llmApiKeyEnvVar = 'A3S_LLM_API_KEY';

		const config: AgentRuntimeConfig = {
			llm: {
				api_url: agentConfig.apiUrl,
				api_key: `\${${llmApiKeyEnvVar}}`,
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
								policies: {
									jwks: agentConfig.oauth2JwksUrl
										? {
												discovered: false,
												url: agentConfig.oauth2JwksUrl
											}
										: {
												discovered: true
											},
									rfc9068: agentConfig.oauth2Rfc9068Enabled
										? {
												resource_server: agentConfig.oauth2ResourceServer ?? ''
											}
										: undefined,
									claims: {}
								}
							}
						: {
								mode: 'api_key',
								api_key: `\${${AGENT_API_KEY_ENV_VAR}}`
							},
			mcp_servers: agentConfig.mcpServers.map((mcpServerUrl) => ({
				url: mcpServerUrl,
				auth: 'none'
			}))
		};

		return {
			runtimeConfig: agentRuntimeConfigSchema.parse(config),
			secretData: {
				[llmApiKeyEnvVar]: agentConfig.apiKey,
				...(agentApiKey ? { [AGENT_API_KEY_ENV_VAR]: agentApiKey } : {})
			}
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
				const annotations = pod.metadata?.annotations;

				return {
					podName: pod.metadata?.name ?? '<unknown-pod>',
					agentName:
						annotations?.[AGENT_NAME_ANNOTATION] ??
						pod.metadata?.labels?.name ??
						pod.metadata?.name ??
						'<unknown-agent>',
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
