# GKE Test Setup

Deploys the full a3s stack on GKE: cluster, Artifact Registry, RBAC, app, and
MCP test server.

All services use are internal. Nothing is exposed to the internet.

## Prerequisites

- Terraform installed
- `gcloud` CLI installed
  - `gke-gcloud-auth-plugin` installed: `gcloud components install gke-gcloud-auth-plugin`
- `kubectl` CLI installed
- `podman`/`docker` for building and pushing images

## 0. GCP project setup

```bash
gcloud auth login
gcloud auth application-default login

PROJECT_ID="prj-a3s"
gcloud projects create "$PROJECT_ID"
gcloud config set project "$PROJECT_ID"

BILLING_ACCOUNT_ID=... # Set a billing account
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"
```

## 1. Deploy Artifact Registry and push images to it

```bash
PROJECT_ID="prj-a3s"
REGION="europe-west1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/a3s"

gcloud auth configure-docker "${REGION}-docker.pkg.dev"

# Create the registry first to thne push images to it.
# The rest of the infra is deployed in step 2.
cp terraform.tfvars.example terraform.tfvars # Adapt if necessary, values should
                                             # correspond to those of PROJECT_ID,
                                             # REGION, and REGISTRY set above
terraform init
terraform apply -target=google_artifact_registry_repository.a3s

# Build and push the images
podman build --arch amd64 -t "${REGISTRY}/agent:latest" ../../agent/
podman build --arch amd64 -t "${REGISTRY}/app:latest"   ../../app/
podman build --arch amd64 -t "${REGISTRY}/mcp:latest"   ../../tests/mcp/
podman push "${REGISTRY}/agent:latest"
podman push "${REGISTRY}/app:latest"
podman push "${REGISTRY}/mcp:latest"
```

## 2. Deploy everything

```bash
terraform apply
```

## 3. Connect to the cluster

```bash
# This command should've been output by terraform upon applying the config
$(terraform output -raw kubeconfig_command)
```

## 4. Access the app

The app isn't exposed externally. Use `kubectl port-forward` to access it:

```bash
kubectl port-forward -n app-ns deploy/app 3000:3000
```

App should be available at `localhost:3000` after that.

## Deploying an agent

When configuring an agent's MCP server URL through the app UI, use the
in-cluster DNS name: `http://mcp-svc.app-ns.svc.cluster.local:3000/mcp`

To access an agent, use `kubectl port-forward` again:

```bash
# Look up the agent pod's name
kubectl get pods -n agents-ns
agent_pod_name=...
kubectl port-forward -n agents-ns "$agent_pod_name" 8000:8000
```

Then use `../cli` to test the agent.

## 5. Tear down

```bash
terraform destroy
```
