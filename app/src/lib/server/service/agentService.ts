import Docker from 'dockerode';
import net from 'node:net';

interface DeployAgentParams {
	model: string;
	name: string;
	description: string;
	instructions: string;
	apiKey: string;
	apiUrl: string;
	mcpServers: string[];
}

class AgentService {
	private _docker: Docker | undefined;

	private getDockerClient(): Docker {
		if (!this._docker) {
			this._docker = new Docker();
		}

		return this._docker;
	}

	private async getFreePort(): Promise<number> {
		return await new Promise((resolve, reject) => {
			const server = net.createServer();
			server.unref();
			server.on('error', reject);

			server.listen(0, '127.0.0.1', () => {
				const address = server.address();

				if (!address || typeof address === 'string') {
					server.close(() => reject(new Error('Failed to resolve free port')));
					return;
				}

				const port = address.port;
				server.close((err) => (err ? reject(err) : resolve(port)));
			});
		});
	}

	private isPortAllocatedError(error: unknown): boolean {
		if (!(error instanceof Error)) {
			return false;
		}

		const message = error.message.toLowerCase();
		return (
			message.includes('port is already allocated') || message.includes('address already in use')
		);
	}

	private async runAndRetryWithFreePort(run: () => Promise<Docker.Container>) {
		const MAX_DEPLOY_RETRIES = 5;

		for (let attempt = 1; attempt <= MAX_DEPLOY_RETRIES; attempt += 1) {
			let container: Docker.Container | undefined;

			try {
				container = await run();
				return container;
			} catch (error) {
				if (container) {
					try {
						await container.remove({ force: true });
					} catch {
						// Best effort cleanup for a partially created container.
					}
				}

				if (this.isPortAllocatedError(error) && attempt < MAX_DEPLOY_RETRIES) {
					continue;
				}

				throw error;
			}
		}

		throw new Error('Failed to deploy agent after exhausting retry attempts');
	}

	async deployAgent(params: DeployAgentParams) {
		const docker = this.getDockerClient();
		const mcpServersValue = params.mcpServers.join(',');

		await this.runAndRetryWithFreePort(async () => {
			const listenPort = await this.getFreePort();
			const portKey = `${listenPort}/tcp`;

			const container = await docker.createContainer({
				Image: 'agent',
				Env: [
					`MODEL=${params.model}`,
					`AGENT_NAME=${params.name}`,
					`AGENT_INSTRUCTIONS=${params.instructions}`,
					`AGENT_DESCRIPTION=${params.description}`,
					`LLM_API_KEY=${params.apiKey}`,
					`LLM_API_URI=${params.apiUrl}`,
					`LISTEN_PORT=${listenPort}`,
					`MCP_SERVERS=${mcpServersValue}`
				],
				OpenStdin: true,
				Tty: true,
				ExposedPorts: {
					[portKey]: {}
				},
				HostConfig: {
					AutoRemove: true,
					PortBindings: {
						[portKey]: [{ HostPort: String(listenPort) }]
					}
				}
			});

			await container.start();

			console.log(`Started local agent container ${container.id} on localhost:${listenPort}`);
			return container;
		});
	}
}

export const containersService = new AgentService();
