variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "zone" {
  type    = string
  default = "europe-west1-b"
}

variable "cluster_name" {
  type    = string
  default = "a3s-gke"
}

variable "app_image" {
  type        = string
  description = "Full Artifact Registry path for the app image (e.g. europe-west1-docker.pkg.dev/my-project/a3s/app:latest)"
}

variable "agent_image" {
  type        = string
  description = "Full Artifact Registry path for the agent image (e.g. europe-west1-docker.pkg.dev/my-project/a3s/agent:latest)"
}

variable "mcp_image" {
  type        = string
  description = "Full Artifact Registry path for the MCP test server image"
}

variable "machine_type" {
  type    = string
  default = "e2-medium"
}

variable "node_count" {
  type    = number
  default = 1
}
