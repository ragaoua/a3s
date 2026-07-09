output "cluster_endpoint" {
  value = google_container_cluster.a3s.endpoint
}

output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.a3s.repository_id}"
}

output "kubeconfig_command" {
  value = "gcloud container clusters get-credentials ${var.cluster_name} --zone ${var.zone} --project ${var.project_id}"
}

output "mcp_cluster_url" {
  value       = "http://mcp-svc.app-ns.svc.cluster.local:3000/mcp"
  description = "MCP server URL reachable from agent pods within the cluster"
}
