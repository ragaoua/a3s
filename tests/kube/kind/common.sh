#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
KIND_DIR="${ROOT_DIR}/tests/kube/kind"
APP_DIR="${ROOT_DIR}/app"
AGENT_DIR="${ROOT_DIR}/agent"
MCP_DIR="${ROOT_DIR}/tests/mcp"

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME-a3s-kind}"
KUBE_CONTEXT="kind-${KIND_CLUSTER_NAME}"

REGISTRY_NAME="a3s-kind-registry"
REGISTRY_PORT=5001

AGENT_IMAGE="localhost:${REGISTRY_PORT}/a3s-agent"
APP_IMAGE="localhost:${REGISTRY_PORT}/a3s-app"
MCP_IMAGE="localhost:${REGISTRY_PORT}/a3s-mcp"

log() {
  # shellcheck disable=SC2059
  echo -e "\033[1;32m⛭ $*\033[0m"
}

kind() {
  KIND_EXPERIMENTAL_PROVIDER="podman" command kind "$@"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    log "Missing required command: ${cmd}" >&2
    exit 1
  fi
}

ensure_registry() {
  if podman inspect "${REGISTRY_NAME}" &>/dev/null; then
    if [ "$(podman inspect -f '{{.State.Running}}' "${REGISTRY_NAME}")" != "true" ]; then
      log "Starting existing registry container..."
      podman start "${REGISTRY_NAME}"
    else
      log "Registry already running."
    fi
  else
    log "Creating registry container..."
    podman run -d --restart=always \
      -p "127.0.0.1:${REGISTRY_PORT}:5000" \
      --name "${REGISTRY_NAME}" \
      registry:2
  fi
}

configure_registry_for_kind() {
  local node="${KIND_CLUSTER_NAME}-control-plane"
  local registry_dir="/etc/containerd/certs.d/localhost:${REGISTRY_PORT}"

  log "Configuring registry for kind node ${node}..."
  podman exec "${node}" mkdir -p "${registry_dir}"
  podman exec -i "${node}" cp /dev/stdin "${registry_dir}/hosts.toml" <<EOF
[host."http://${REGISTRY_NAME}:5000"]
  capabilities = ["pull", "resolve"]
EOF

  if ! podman inspect -f '{{json .NetworkSettings.Networks.kind}}' "${REGISTRY_NAME}" 2>/dev/null | grep -q 'kind'; then
    log "Connecting registry to kind network..."
    podman network connect kind "${REGISTRY_NAME}"
  fi
}

ensure_dependencies() {
  log "Checking dependencies..."
  require_cmd kind
  require_cmd kubectl
  require_cmd podman
}

ensure_kind_cluster() {
  log "Ensuring kind cluster '${KIND_CLUSTER_NAME}' exists..."
  if kind get clusters | grep -qx "${KIND_CLUSTER_NAME}"; then
    log "Cluster already exists, skipping creation."
  else
    kind create cluster --name "${KIND_CLUSTER_NAME}" --config "${KIND_DIR}/kind.yaml"
  fi
}

build_images() {
  log "Building agent image..."
  podman build -t "${AGENT_IMAGE}" "${AGENT_DIR}"

  log "Building app image..."
  podman build -t "${APP_IMAGE}" "${APP_DIR}"

  log "Building MCP image..."
  podman build -t "${MCP_IMAGE}" "${MCP_DIR}"
}

push_images() {
  log "Pushing images to local registry..."
  podman push --tls-verify=false "${AGENT_IMAGE}"
  podman push --tls-verify=false "${APP_IMAGE}"
  podman push --tls-verify=false "${MCP_IMAGE}"
}

apply_rbac_and_namespaces() {
  log "Applying namespaces, service account, role, and role binding..."
  kubectl --context "${KUBE_CONTEXT}" apply \
    -f "${KIND_DIR}/app-ns.yaml" \
    -f "${KIND_DIR}/agents-ns.yaml" \
    -f "${KIND_DIR}/sa.yaml" \
    -f "${KIND_DIR}/role.yaml" \
    -f "${KIND_DIR}/role_binding.yaml"
}

apply_mcp() {
  log "Applying MCP pod..."
  kubectl --context "${KUBE_CONTEXT}" apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  labels:
    run: mcp
  name: mcp
  namespace: app-ns
spec:
  restartPolicy: Never
  containers:
    - name: mcp
      image: ${MCP_IMAGE}
      imagePullPolicy: Always
      args:
        - --no-auth
        - --stateless
      env:
        - name: HOST
          value: 0.0.0.0
        - name: PORT
          value: "3000"
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-svc
  namespace: app-ns
spec:
  type: NodePort
  selector:
    run: mcp
  ports:
    - protocol: TCP
      port: 3000
      targetPort: 3000
      nodePort: 30082
EOF
}

get_mcp_node_internal_ip() {
  kubectl --context "${KUBE_CONTEXT}" get nodes \
    -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}'
}

prepare_kind_cluster() {
  ensure_dependencies
  ensure_registry
  ensure_kind_cluster
  configure_registry_for_kind
  build_images
  push_images
  apply_rbac_and_namespaces
  apply_mcp
}
