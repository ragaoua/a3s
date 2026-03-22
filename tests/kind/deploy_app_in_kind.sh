#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
KIND_DIR="${ROOT_DIR}/tests/kind"
APP_DIR="${ROOT_DIR}/app"
AGENT_DIR="${ROOT_DIR}/agent"

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME-a3s-kind}"
KUBE_CONTEXT="kind-${KIND_CLUSTER_NAME}"

AGENT_IMAGE="localhost/a3s-agent"
APP_IMAGE="localhost/a3s-app"

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

load_image_to_kind() {
  local image="$1"
  kind load image-archive --name "${KIND_CLUSTER_NAME}" <(podman save "${image}" --format oci-archive)
}

log "Checking dependencies..."
require_cmd kind
require_cmd kubectl
require_cmd podman

log "Ensuring kind cluster '${KIND_CLUSTER_NAME}' exists..."
if kind get clusters | grep -qx "${KIND_CLUSTER_NAME}"; then
  log "Cluster already exists, skipping creation."
else
  kind create cluster --name "${KIND_CLUSTER_NAME}" --config "${KIND_DIR}/kind.yaml"
fi

log "Building agent image..."
podman build -t "${AGENT_IMAGE}" "${AGENT_DIR}"

log "Building app image..."
podman build -t "${APP_IMAGE}" "${APP_DIR}"

log "Loading images into kind cluster..."
load_image_to_kind "${AGENT_IMAGE}"
load_image_to_kind "${APP_IMAGE}"

log "Applying namespaces, service account, role, and role binding..."
kubectl --context "${KUBE_CONTEXT}" apply \
  -f "${KIND_DIR}/app-ns.yaml" \
  -f "${KIND_DIR}/agents-ns.yaml" \
  -f "${KIND_DIR}/sa.yaml" \
  -f "${KIND_DIR}/role.yaml" \
  -f "${KIND_DIR}/role_binding.yaml"

log "Applying app pod..."
kubectl --context "${KUBE_CONTEXT}" apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  labels:
    run: app
  name: app
  namespace: app-ns
spec:
  serviceAccountName: app-sa
  restartPolicy: Never
  containers:
    - name: app
      image: ${APP_IMAGE}
      imagePullPolicy: Never
      env:
        - name: K8S_AGENTS_NAMESPACE
          value: agents-ns
        - name: ORIGIN
          value: http://localhost:8080
        - name: NODE_TLS_REJECT_UNAUTHORIZED
          value: "0"
EOF

log "Applying NodePort service..."
kubectl --context "${KUBE_CONTEXT}" apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: app-svc
  namespace: app-ns
spec:
  type: NodePort
  selector:
    run: app
  ports:
    - protocol: TCP
      port: 3000
      targetPort: 3000
      nodePort: 30080
EOF

log "Done. App should be reachable at http://localhost:8080"
