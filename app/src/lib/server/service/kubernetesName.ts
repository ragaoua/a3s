const MAX_KUBERNETES_NAME_LENGTH = 63;

export const AGENT_NAME_ANNOTATION = 'a3s.dev/agent-name';

export function sanitizeKubernetesName(value: string): string {
	const sanitized = value
		.trim()
		.toLowerCase()
		.replace(/[^a-z0-9-]+/g, '-')
		.replace(/-+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, MAX_KUBERNETES_NAME_LENGTH)
		.replace(/-+$/g, '');

	return sanitized || 'agent';
}
