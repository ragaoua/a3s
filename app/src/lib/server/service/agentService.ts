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

class AgentService {
	private getRequiredEnv(name: string): string {
		const value = env[name];

		if (!value) {
			throw new Error(`Missing required environment variable: ${name}`);
		}

		return value;
	}

	private generateAgentApiKey(): string {
		return randomBytes(32).toString('hex');
	}

	async deployToKubernetes(params: DeployAgentParams) {
		const clusterName = this.getRequiredEnv('K8S_CLUSTER_NAME');
		const server = this.getRequiredEnv('K8S_SERVER_URL');
		const serviceAccount = this.getRequiredEnv('K8S_SERVICE_ACCOUNT');
		const serviceAccountToken = this.getRequiredEnv('K8S_SERVICE_ACCOUNT_TOKEN');
		const namespace = this.getRequiredEnv('K8S_NAMESPACE');
		const caData = this.getRequiredEnv('K8S_CA_DATA');

		const kc = new KubeConfig();

		kc.loadFromOptions({
			clusters: [
				{
					name: clusterName,
					server,
					caData
				}
			],
			users: [
				{
					name: serviceAccount,
					token: serviceAccountToken
				}
			],
			contexts: [
				{
					cluster: clusterName,
					user: serviceAccount,
					namespace
				}
			]
		});

		const mcpServersValue = params.mcpServers.join(',');
		const listenPort = 10000;

		const authVars: V1EnvVar[] = [];
		if (params.oauth2IssuerUrl) {
			authVars.push({ name: 'OAUTH2_ISSUER_URL', value: params.oauth2IssuerUrl });
			if (params.oauth2JwksUrl) {
				authVars.push({ name: 'OAUTH2_JWKS_URL', value: params.oauth2JwksUrl });
			}
			console.log('Agent will be configured with OAuth2 Authorization.');
		} else {
			const agentApiKey = this.generateAgentApiKey();
			authVars.push({ name: 'AGENT_API_KEY', value: agentApiKey });
			console.log(
				`Agent will be configured with API Key Authorization.\nUse API Key ${agentApiKey}`
			);
		}

		const core = kc.makeApiClient(CoreV1Api);

		const pod = await core.createNamespacedPod({
			namespace,
			body: {
				apiVersion: 'v1',
				kind: 'Pod',
				metadata: {
					generateName: params.name.toLowerCase()
				},
				spec: {
					restartPolicy: 'Never',
					containers: [
						{
							name: params.name.toLowerCase(),
							image: 'localhost/a3s-agent',
							imagePullPolicy: 'Never',
							env: [
								{ name: 'MODEL', value: params.model },
								{ name: 'AGENT_NAME', value: params.name },
								{ name: 'AGENT_INSTRUCTIONS', value: params.instructions },
								{ name: 'AGENT_DESCRIPTION', value: params.description },
								{ name: 'LLM_API_KEY', value: params.apiKey },
								{ name: 'LLM_API_URI', value: params.apiUrl },
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
	}

	private async getNamespace(): Promise<string> {
		const namespaceFromEnv = env.K8S_NAMESPACE;
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
			'Missing Kubernetes namespace. Set K8S_NAMESPACE or ensure in-cluster namespace file is mounted.'
		);
	}

	async deployToInternalKubernetesCluster(params: DeployAgentParams) {
		const kc = new KubeConfig();
		kc.loadFromCluster();

		const mcpServersValue = params.mcpServers.join(',');
		const listenPort = 10000;

		const authVars: V1EnvVar[] = [];
		if (params.oauth2IssuerUrl) {
			authVars.push({ name: 'OAUTH2_ISSUER_URL', value: params.oauth2IssuerUrl });
			if (params.oauth2JwksUrl) {
				authVars.push({ name: 'OAUTH2_JWKS_URL', value: params.oauth2JwksUrl });
			}
			console.log('Agent will be configured with OAuth2 Authorization.');
		} else {
			const agentApiKey = this.generateAgentApiKey();
			authVars.push({ name: 'AGENT_API_KEY', value: agentApiKey });
			console.log(
				`Agent will be configured with API Key Authorization.\nUse API Key ${agentApiKey}`
			);
		}

		const namespace = await this.getNamespace();
		const core = kc.makeApiClient(CoreV1Api);

		const pod = await core.createNamespacedPod({
			namespace,
			body: {
				apiVersion: 'v1',
				kind: 'Pod',
				metadata: {
					generateName: params.name.toLowerCase()
				},
				spec: {
					restartPolicy: 'Never',
					containers: [
						{
							name: params.name.toLowerCase(),
							image: 'localhost/a3s-agent',
							imagePullPolicy: 'Never',
							env: [
								{ name: 'MODEL', value: params.model },
								{ name: 'AGENT_NAME', value: params.name },
								{ name: 'AGENT_INSTRUCTIONS', value: params.instructions },
								{ name: 'AGENT_DESCRIPTION', value: params.description },
								{ name: 'LLM_API_KEY', value: params.apiKey },
								{ name: 'LLM_API_URI', value: params.apiUrl },
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
	}
}

export const containersService = new AgentService();
