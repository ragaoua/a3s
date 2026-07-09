# --- Namespaces ---

resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = "app-ns"
  }

  depends_on = [google_container_node_pool.default]
}

resource "kubernetes_namespace_v1" "agents" {
  metadata {
    name = "agents-ns"
  }

  depends_on = [google_container_node_pool.default]
}

# --- RBAC ---

resource "kubernetes_service_account_v1" "app" {
  metadata {
    name      = "app-sa"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
}

resource "kubernetes_role_v1" "agent_pod_operator" {
  metadata {
    name      = "agent-pod-operator"
    namespace = kubernetes_namespace_v1.agents.metadata[0].name
  }

  rule {
    api_groups = ["apps"]
    resources  = ["deployments"]
    verbs      = ["create", "patch", "list", "delete"]
  }

  rule {
    api_groups = [""]
    resources  = ["configmaps", "secrets"]
    verbs      = ["create", "delete"]
  }
}

resource "kubernetes_role_binding_v1" "pod_creator" {
  metadata {
    name      = "pod-creator-binding"
    namespace = kubernetes_namespace_v1.agents.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.app.metadata[0].name
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }

  role_ref {
    kind      = "Role"
    name      = kubernetes_role_v1.agent_pod_operator.metadata[0].name
    api_group = "rbac.authorization.k8s.io"
  }
}

# --- App ---

resource "kubernetes_config_map_v1" "app_config" {
  metadata {
    name      = "app-config"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }

  data = {
    "config.yaml" = yamlencode({
      agentImage = var.agent_image
      deployment = {
        mode            = "inCluster"
        agentsNamespace = "agents-ns"
      }
      auth = {
        enabled = false
      }
    })
  }
}

resource "kubernetes_deployment_v1" "app" {
  metadata {
    name      = "app"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      run = "app"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        run = "app"
      }
    }

    template {
      metadata {
        labels = {
          run = "app"
        }
      }

      spec {
        service_account_name = kubernetes_service_account_v1.app.metadata[0].name

        container {
          name              = "app"
          image             = var.app_image
          image_pull_policy = "Always"

          port {
            container_port = 3000
          }

          env {
            name  = "NODE_EXTRA_CA_CERTS"
            value = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
          }

          volume_mount {
            name       = "app-config"
            mount_path = "/app/config.yaml"
            sub_path   = "config.yaml"
            read_only  = true
          }
        }

        volume {
          name = "app-config"

          config_map {
            name = kubernetes_config_map_v1.app_config.metadata[0].name
          }
        }
      }
    }
  }
}

# --- MCP test server ---

resource "kubernetes_pod_v1" "mcp" {
  metadata {
    name      = "mcp"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      run = "mcp"
    }
  }

  spec {
    restart_policy = "Never"

    container {
      name              = "mcp"
      image             = var.mcp_image
      image_pull_policy = "Always"
      args              = ["--no-auth", "--stateless"]

      env {
        name  = "HOST"
        value = "0.0.0.0"
      }

      env {
        name  = "PORT"
        value = "3000"
      }
    }
  }
}

resource "kubernetes_service_v1" "mcp" {
  metadata {
    name      = "mcp-svc"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }

  spec {
    type = "ClusterIP"

    selector = {
      run = "mcp"
    }

    port {
      protocol    = "TCP"
      port        = 3000
      target_port = 3000
    }
  }
}
