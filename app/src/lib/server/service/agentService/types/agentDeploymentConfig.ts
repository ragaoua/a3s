import type { AgentRuntimeConfig } from '$lib/types/agentRuntimeConfig';

export interface AgentDeploymentConfig {
	runtimeConfig: AgentRuntimeConfig;
	secretData: Record<string, string>;
}
