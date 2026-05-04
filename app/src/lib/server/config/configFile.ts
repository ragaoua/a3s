import z from 'zod';
import {
	disabledAuthConfigSchema,
	enabledAuthConfigSchema,
	inClusterDeploymentSchema,
	remoteDeploymentSchema
} from './appConfig';

const configFileEnabledAuthSchema = enabledAuthConfigSchema
	.omit({ clientSecret: true, secret: true, publicClient: true })
	.extend({
		publicClient: z.boolean().default(false)
	});

const configFileAuthSchema = z.discriminatedUnion('enabled', [
	configFileEnabledAuthSchema,
	disabledAuthConfigSchema
]);

const configFileRemoteDeploymentSchema = remoteDeploymentSchema.omit({ serviceAccountToken: true });

const configFileDeploymentSchema = z.discriminatedUnion('mode', [
	inClusterDeploymentSchema,
	configFileRemoteDeploymentSchema,
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
	deployment: configFileDeploymentSchema,
	auth: configFileAuthSchema
});
export type ConfigFile = z.infer<typeof configFileSchema>;
