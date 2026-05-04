import { CoreV1Api, KubeConfig } from '@kubernetes/client-node';
import { randomBytes } from 'node:crypto';
import YAML from 'yaml';
import { agentRuntimeConfigSchema, type AgentRuntimeConfig } from '$lib/types/agentRuntimeConfig';
import type { AgentConfigForm } from '$lib/types/agentConfigForm';
import type { Oauth2PoliciesForm } from '$lib/types/agentConfigForm/oauth2Policies';
import { AGENT_NAME_ANNOTATION, sanitizeKubernetesName } from '../kubernetesName';
import type { AgentSummary } from './types/agentSummary';
import type { AgentDeploymentConfig } from './types/agentDeploymentConfig';
import type { Subagents } from '$lib/types/agentRuntimeConfig/subagent';
import { policiesSchema, type OAuth2RuntimePolicies } from '$lib/types/agentRuntimeConfig/auth';

const LLM_API_KEY_ENV_VAR = 'A3S_LLM_API_KEY';
const AGENT_API_KEY_ENV_VAR = 'A3S_AGENT_API_KEY';
const INTROSPECTION_CLIENT_SECRET_ENV_VAR = 'A3S_INTROSPECTION_CLIENT_SECRET';
const MCP_SERVER_CLIENT_SECRET_ENV_VAR_PREFIX = 'A3S_MCP_SERVER_CLIENT_SECRET';
const SUBAGENT_CLIENT_SECRET_ENV_VAR_PREFIX = 'A3S_SUBAGENT_CLIENT_SECRET';
const SUBAGENT_API_KEY_ENV_VAR_PREFIX = 'A3S_SUBAGENT_API_KEY';

export abstract class AgentService {
	protected constructor(private readonly a3sAgentImage: string) {}
	protected abstract getKubeConfig(): KubeConfig;

	protected abstract getNamespace(): Promise<string>;

	async deployToKubernetes(agentConfig: AgentConfigForm): Promise<{ agentApiKey?: string }> {
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
		const skillConfigMaps = agentConfig.skills.map((skill) => ({
			skillName: skill.name,
			configMapName: `a3s-${kubernetesAgentName}-skill-${skill.name}-${resourceSuffix}`,
			body: buildSkillMarkdown(skill)
		}));
		let configMapCreated = false;
		let secretCreated = false;
		const createdSkillConfigMaps: string[] = [];

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

			for (const skill of skillConfigMaps) {
				await core.createNamespacedConfigMap({
					namespace,
					body: {
						apiVersion: 'v1',
						kind: 'ConfigMap',
						metadata: {
							name: skill.configMapName,
							labels: {
								run: 'agent',
								'a3s.dev/agent': kubernetesAgentName,
								'a3s.dev/skill': skill.skillName
							}
						},
						data: {
							'SKILL.md': skill.body
						}
					}
				});
				createdSkillConfigMaps.push(skill.configMapName);
			}

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
								image: this.a3sAgentImage,
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
								projected: {
									sources: [
										{
											configMap: {
												name: configMapName,
												items: [{ key: 'agent.yaml', path: 'agent.yaml' }]
											}
										},
										...skillConfigMaps.map((skill) => ({
											configMap: {
												name: skill.configMapName,
												items: [{ key: 'SKILL.md', path: `skills/${skill.skillName}/SKILL.md` }]
											}
										}))
									]
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
			for (const skillConfigMapName of createdSkillConfigMaps) {
				try {
					await core.deleteNamespacedConfigMap({
						name: skillConfigMapName,
						namespace
					});
				} catch (cleanupError) {
					console.warn(`Failed to clean up skill config map ${skillConfigMapName}:`, cleanupError);
				}
			}

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
		const secretData: Record<string, string> = {
			[LLM_API_KEY_ENV_VAR]: agentConfig.apiKey
		};

		if (agentConfig.authMode === 'apiKey') {
			const agentApiKey = randomBytes(32).toString('hex');
			secretData[AGENT_API_KEY_ENV_VAR] = agentApiKey;
		}

		const subagents: Subagents = {};
		agentConfig.subagents.forEach((subagent, index) => {
			switch (subagent.authMode) {
				case 'none':
					subagents[subagent.name] = {
						url: subagent.url,
						type: subagent.type,
						auth: 'none'
					};
					break;
				case 'oauth_token_forward':
					subagents[subagent.name] = {
						url: subagent.url,
						type: subagent.type,
						auth: { mode: 'oauth_token_forward' }
					};
					break;
				case 'oauth_client_credentials': {
					const clientSecretEnvVar = `${SUBAGENT_CLIENT_SECRET_ENV_VAR_PREFIX}${index}`;
					secretData[clientSecretEnvVar] = subagent.clientSecret;
					subagents[subagent.name] = {
						url: subagent.url,
						type: subagent.type,
						auth: {
							mode: 'oauth_client_credentials',
							client_id: subagent.clientId,
							client_secret: `\${${clientSecretEnvVar}}`,
							auth_method: subagent.authMethod,
							token_endpoint: subagent.tokenEndpoint
						}
					};
					break;
				}
				case 'oauth_token_exchange': {
					const clientSecretEnvVar = `${SUBAGENT_CLIENT_SECRET_ENV_VAR_PREFIX}${index}`;
					secretData[clientSecretEnvVar] = subagent.clientSecret;
					subagents[subagent.name] = {
						url: subagent.url,
						type: subagent.type,
						auth: {
							mode: 'oauth_token_exchange',
							client_id: subagent.clientId,
							client_secret: `\${${clientSecretEnvVar}}`,
							auth_method: subagent.authMethod,
							...(subagent.tokenEndpoint !== undefined
								? { discovered: false, token_endpoint: subagent.tokenEndpoint }
								: { discovered: true })
						}
					};
					break;
				}
				case 'apiKey': {
					const apiKeyEnvVar = `${SUBAGENT_API_KEY_ENV_VAR_PREFIX}${index}`;
					secretData[apiKeyEnvVar] = subagent.apiKey;
					subagents[subagent.name] = {
						url: subagent.url,
						type: subagent.type,
						auth: {
							mode: 'api_key',
							api_key: `\${${apiKeyEnvVar}}`
						}
					};
					break;
				}
			}
		});

		const config: AgentRuntimeConfig = {
			llm: {
				api_url: agentConfig.apiUrl,
				api_key: `\${${LLM_API_KEY_ENV_VAR}}`,
				model: agentConfig.model
			},
			agent: {
				name: agentConfig.name,
				description: agentConfig.description,
				instructions: agentConfig.instructions,
				subagents
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
								policies: buildOauth2Policies(agentConfig.oauth2Policies, secretData)
							}
						: {
								mode: 'api_key',
								api_key: `\${${AGENT_API_KEY_ENV_VAR}}`
							},
			mcp_servers: agentConfig.mcpServers.map((mcpServer, index) => {
				switch (mcpServer.authMode) {
					case 'none':
						return {
							url: mcpServer.url,
							auth: 'none'
						};
					case 'oauth_token_forward':
						return {
							url: mcpServer.url,
							auth: {
								mode: 'oauth_token_forward'
							}
						};
					case 'oauth_client_credentials': {
						const clientSecretEnvVar = `${MCP_SERVER_CLIENT_SECRET_ENV_VAR_PREFIX}${index}`;
						secretData[clientSecretEnvVar] = mcpServer.clientSecret;
						return {
							url: mcpServer.url,
							auth: {
								mode: 'oauth_client_credentials',
								client_id: mcpServer.clientId,
								client_secret: `\${${clientSecretEnvVar}}`,
								auth_method: mcpServer.authMethod,
								token_endpoint: mcpServer.tokenEndpoint
							}
						};
					}
					case 'oauth_token_exchange': {
						const clientSecretEnvVar = `${MCP_SERVER_CLIENT_SECRET_ENV_VAR_PREFIX}${index}`;
						secretData[clientSecretEnvVar] = mcpServer.clientSecret;
						return {
							url: mcpServer.url,
							auth: {
								mode: 'oauth_token_exchange',
								client_id: mcpServer.clientId,
								client_secret: `\${${clientSecretEnvVar}}`,
								auth_method: mcpServer.authMethod,
								...(mcpServer.tokenEndpoint !== undefined
									? {
											discovered: false,
											token_endpoint: mcpServer.tokenEndpoint
										}
									: {
											discovered: true
										})
							}
						};
					}
				}
			}),
			logging: {
				level: 'INFO',
				format: 'plain'
			}
		};

		return {
			runtimeConfig: agentRuntimeConfigSchema.parse(config),
			secretData
		};
	}

	async deleteAgent(podName: string): Promise<void> {
		const kc = this.getKubeConfig();
		const namespace = await this.getNamespace();
		const core = kc.makeApiClient(CoreV1Api);

		const pod = await core.readNamespacedPod({ name: podName, namespace });

		const configMapNames = new Set<string>();
		const secretNames = new Set<string>();

		for (const volume of pod.spec?.volumes ?? []) {
			for (const source of volume.projected?.sources ?? []) {
				if (source.configMap?.name) {
					configMapNames.add(source.configMap.name);
				}
			}
		}

		for (const container of pod.spec?.containers ?? []) {
			for (const env of container.env ?? []) {
				const secretName = env.valueFrom?.secretKeyRef?.name;
				if (secretName) {
					secretNames.add(secretName);
				}
			}
		}

		await core.deleteNamespacedPod({ name: podName, namespace });

		for (const configMapName of configMapNames) {
			try {
				await core.deleteNamespacedConfigMap({ name: configMapName, namespace });
			} catch (error) {
				console.warn(`Failed to delete config map ${configMapName}:`, error);
			}
		}

		for (const secretName of secretNames) {
			try {
				await core.deleteNamespacedSecret({ name: secretName, namespace });
			} catch (error) {
				console.warn(`Failed to delete secret ${secretName}:`, error);
			}
		}
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

function buildSkillMarkdown(skill: { name: string; description: string; content: string }): string {
	const frontmatter = YAML.stringify({
		name: skill.name,
		description: skill.description
	}).trimEnd();
	const content = skill.content.endsWith('\n') ? skill.content : `${skill.content}\n`;
	return `---\n${frontmatter}\n---\n\n${content}`;
}

function buildOauth2Policies(
	formPolicies: Oauth2PoliciesForm,
	secretData: Record<string, string>
): OAuth2RuntimePolicies {
	const policies: OAuth2RuntimePolicies = {};

	if (formPolicies.jwtEnabled) {
		policies.jwt = {
			jwks:
				formPolicies.jwt.jwksSource === 'discovered'
					? { discovered: true }
					: { discovered: false, url: formPolicies.jwt.jwksUrl },
			rfc9068: formPolicies.jwt.rfc9068Enabled
				? {
						resource_server: formPolicies.jwt.rfc9068ResourceServer
					}
				: undefined,
			claims:
				formPolicies.jwt.claims.length > 0
					? Object.fromEntries(formPolicies.jwt.claims.map((claim) => [claim.key, claim.value]))
					: undefined
		};
	}

	if (formPolicies.introspectionEnabled) {
		secretData[INTROSPECTION_CLIENT_SECRET_ENV_VAR] = formPolicies.introspection.clientSecret;

		policies.introspection = {
			client_id: formPolicies.introspection.clientId,
			client_secret: `\${${INTROSPECTION_CLIENT_SECRET_ENV_VAR}}`,
			auth_method: formPolicies.introspection.authMethod,
			...(formPolicies.introspection.endpointSource === 'discovered'
				? {
						discovered: true
					}
				: {
						discovered: false,
						endpoint: formPolicies.introspection.endpoint
					})
		};
	}

	return policiesSchema.parse(policies);
}
