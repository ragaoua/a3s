import z from 'zod';

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
};
