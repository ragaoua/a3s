#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

prepare_kind_cluster

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
        - name: A3S_AGENT_IMAGE
          value: localhost/a3s-agent
        - name: K8S_AGENTS_NAMESPACE
          value: agents-ns
        - name: ORIGIN
          value: http://localhost:8080
        - name: NODE_TLS_REJECT_UNAUTHORIZED
          value: "0"
---
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

MCP_NODE_IP="$(get_mcp_node_internal_ip)"
log "Done."
log "App should be reachable at http://localhost:8080"
log "MCP server should be reachable at http://${MCP_NODE_IP}:30082/mcp"
