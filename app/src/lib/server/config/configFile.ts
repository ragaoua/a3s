import z from 'zod';
import { inClusterDeploymentSchema, remoteDeploymentSchema } from './appConfig';

const configFileDeploymentSchema = z.discriminatedUnion('mode', [
	inClusterDeploymentSchema,
	remoteDeploymentSchema,
	z.object({
		mode: z.literal('auto'),
		agentsNamespace: z.string().optional(),
		clusterName: z.string().optional(),
		server: z.string().optional(),
		serviceAccount: z.string().optional(),
		serviceAccountNamespace: z.string().optional(),
		caData: z.string().optional() // Base64-encoded
	})
]);
export type ConfigFileDeploymentSchema = z.infer<typeof configFileDeploymentSchema>;

export const configFileSchema = z.object({
	agentImage: z.string(),
	deployment: configFileDeploymentSchema
});
export type ConfigFile = z.infer<typeof configFileSchema>;
