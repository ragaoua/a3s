import z from 'zod';

export const enabledAuthConfigSchema = z.object({
	enabled: z.literal(true),
	issuerUrl: z.url(),
	clientId: z.string().min(1),
	clientSecret: z.string().min(1).optional(),
	publicClient: z.boolean(),
	secret: z.string().min(1)
});
export type EnabledAuthConfig = z.infer<typeof enabledAuthConfigSchema>;

export const disabledAuthConfigSchema = z.object({
	enabled: z.literal(false)
});
export type DisabledAuthConfig = z.infer<typeof disabledAuthConfigSchema>;

export const authConfigSchema = z.discriminatedUnion('enabled', [
	enabledAuthConfigSchema,
	disabledAuthConfigSchema
]);
export type AuthConfig = z.infer<typeof authConfigSchema>;

export const inClusterDeploymentSchema = z.object({
	mode: z.literal('inCluster'),
	agentsNamespace: z.string().optional()
});
export type InClusterDeployment = z.infer<typeof inClusterDeploymentSchema>;

export const remoteDeploymentSchema = z.object({
	mode: z.literal('remote'),
	agentsNamespace: z.string(),
	clusterName: z.string(),
	server: z.string(),
	serviceAccount: z.string(),
	serviceAccountNamespace: z.string(),
	serviceAccountToken: z.string(),
	caData: z.string() // Base64-encoded
});
export type RemoteDeployment = z.infer<typeof remoteDeploymentSchema>;

export type Deployment = InClusterDeployment | RemoteDeployment;

export type AppConfig = {
	agentImage: string;
	deployment: Deployment;
	auth: AuthConfig;
};
