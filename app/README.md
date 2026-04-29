## a3s app

The a3s app provides a centralized platform for running agents on any
Kubernetes environment.

For each deployment request, the app creates a Kubernetes pod running an [a3s
agent](../agent).

When selecting API Key auth mode, the platform generates an API Key and
displays it to the user.

### Running the platform

```bash
cd app
bun ci
bun run dev
```

### Kubernetes deployment modes

Regarding Kubernetes deployment of agents, the platform operates in 2 modes:

- **Remote cluster deployment**: deploys to a remote Kubernetes cluster.
- **In-cluster deployment**: if the app/platform itself is running inside of a
  Kubernetes cluster, it can be configured to deploy to that same cluster,
  using the credentials of the service account used by the app's pod.

In any case, a service account must be configured with proper permissions in
the namespace dedicated to running agents. It must be able to :

- Create and list pods
- Create and delete secrets and config maps

Use `A3S_AGENT_IMAGE` to configure the container image used for agent pods (e.g.
`localhost/a3s-agent` for local development).

Use `K8S_AGENTS_NAMESPACE` to configure the namespace in which the agent pods
will be deployed.

Use `K8S_DEPLOY_MODE` to select the deployment mode:

- `inCluster` for in-cluster deployment. In that case, it is expected that the
  pod running the platform uses the service account mentioned above.
  If `K8S_AGENTS_NAMESPACE` is not set, the platform will try and fetch the
  service account's namespace and use it
- `remote`: in addition to `K8S_AGENTS_NAMESPACE`, set:
  - `K8S_CLUSTER_NAME`
  - `K8S_SERVER_URL`: the URL to the Kubernetes cluster
  - `K8S_SERVICE_ACCOUNT`: the service account mentioned earlier
  - `K8S_SERVICE_ACCOUNT_TOKEN`: a valid token for the service account
  - `K8S_SERVICE_ACCOUNT_NAMESPACE`: the namespace in which the service account
    lives
  - `K8S_CA_DATA`: base64-encoded certificate of the certificate authority
    that signed the Kubernetes API server’s certificate.
- `auto` (default): automatically checks the runtime environment to determine
  if it is running inside of a Kubernetes cluster, in which case the
  `inCluster` mode will be enabled. Otherwise, `remote` mode will be set.
