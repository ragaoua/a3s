#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

prepare_kind_cluster

log "Building app..."
bun --cwd="${APP_DIR}" run build

MCP_NODE_IP="$(get_mcp_node_internal_ip)"
log "MCP server should be reachable at http://${MCP_NODE_IP}:30082/mcp"

log "Generating token for service account app-sa..."
sa_token="$(
  kubectl --context "${KUBE_CONTEXT}" \
    create token app-sa -n app-ns
)"

log "Reading Kubernetes API server URL and CA data..."
k8s_server_url="$(
  kubectl config view --raw --minify --context "${KUBE_CONTEXT}" \
    -o jsonpath='{.clusters[0].cluster.server}'
)"
k8s_ca_data="$(
  kubectl config view --raw --minify --context "${KUBE_CONTEXT}" \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}'
)"

config_path="${APP_DIR}/build/config.yaml"
log "Writing app config to ${config_path}..."
cat >"${config_path}" <<EOF
agentImage: ${A3S_AGENT_IMAGE}
deployment:
  mode: remote
  clusterName: a3s-kind
  server: ${k8s_server_url}
  caData: ${k8s_ca_data}
  serviceAccount: app-sa
  serviceAccountNamespace: app-ns
  agentsNamespace: agents-ns
EOF

log "Running app..."
A3S_CONFIG_PATH="${config_path}" \
  K8S_SERVICE_ACCOUNT_TOKEN="$sa_token" \
  ORIGIN="http://localhost:3000" \
  NODE_TLS_REJECT_UNAUTHORIZED="0" \
  bun --cwd="${APP_DIR}" build/index.js
