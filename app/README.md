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
cp config.example.yaml config.yaml  # then edit it
bun run dev
```

### Configuration

The app reads its configuration from a YAML file (default: `./config.yaml`,
override with the `A3S_CONFIG_PATH` env var). See
[`config.example.yaml`](./config.example.yaml) for a fully commented template.

The only secret read from the environment is `K8S_SERVICE_ACCOUNT_TOKEN`,
required when the deployment mode resolves to `remote`.

### Kubernetes deployment modes

Regarding Kubernetes deployment of agents, the platform operates in 2 modes:

- **Remote cluster deployment**: deploys to a remote Kubernetes cluster.
- **In-cluster deployment**: if the app/platform itself is running inside of a
  Kubernetes cluster, it can be configured to deploy to that same cluster,
  using the credentials of the service account used by the app's pod.

In any case, a service account must be configured with proper permissions in
the namespace dedicated to running agents. It must be able to:

- Create and list pods
- Create and delete secrets and config maps

The mode is selected via `deployment.mode` in `config.yaml`:

- `inCluster`: in-cluster deployment. The pod running the platform must use
  the service account mentioned above. If `deployment.agentsNamespace` is not
  set, the platform will fall back to the service account's namespace.
- `remote`: in addition to `deployment.agentsNamespace`, set:
  - `deployment.clusterName`
  - `deployment.server`: the URL to the Kubernetes cluster
  - `deployment.serviceAccount`: the service account mentioned above
  - `deployment.serviceAccountNamespace`: the namespace in which the service
    account lives
  - `deployment.caData`: base64-encoded certificate of the certificate
    authority that signed the Kubernetes API server's certificate
  - `K8S_SERVICE_ACCOUNT_TOKEN` (env var): a valid token for the service
    account
- `auto` (default): automatically checks the runtime environment to determine
  if it is running inside of a Kubernetes cluster, in which case the
  `inCluster` mode will be enabled. Otherwise, `remote` mode will be set.

`agentImage` configures the container image used for agent pods (e.g.
`localhost/a3s-agent` for local development).
