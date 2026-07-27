import type { AgentRuntimeConfig } from '$lib/types/agentRuntimeConfig';

export interface AgentDeploymentConfig {
	runtimeConfig: AgentRuntimeConfig;
	secretData: Record<string, string>;
	// The plaintext API key, present only when API-key auth is enabled. The
	// config stores just its hash, so this is surfaced once to the caller for
	// display and never written to the deployed Secret or ConfigMap.
	agentApiKey?: string;
}
