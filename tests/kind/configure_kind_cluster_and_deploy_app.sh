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

log "Running app..."
K8S_SERVER_URL="$k8s_server_url" \
  K8S_CA_DATA="$k8s_ca_data" \
  K8S_SERVICE_ACCOUNT_TOKEN="$sa_token" \
  K8S_CLUSTER_NAME=a3s-kind \
  K8S_SERVICE_ACCOUNT="app-sa" \
  K8S_SERVICE_ACCOUNT_NAMESPACE=app-ns \
  K8S_AGENTS_NAMESPACE=agents-ns \
  ORIGIN="http://localhost:3000" \
  NODE_TLS_REJECT_UNAUTHORIZED="0" \
  bun --cwd="${APP_DIR}" build/index.js
