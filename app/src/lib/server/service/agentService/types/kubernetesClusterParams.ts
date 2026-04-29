export interface KubernetesClusterParams {
	clusterName: string;
	server: string;
	serviceAccount: string;
	serviceAccountToken: string;
	serviceAccountNamespace: string;
	agentsNamespace: string;
	caData: string;
}
