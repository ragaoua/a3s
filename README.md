# a3s

a3s stands for Agent as a Service. This project is comprised of 2 components:

1. The [agent](agent/) engine, which provides a flexible interface for running
   custom A2A agents, configurable with authentication and MCP integration.
2. The [app](app): a web platform to configure, manage and deploy agents on
   Kubernetes.

While the platform relies entirely on the a3s agent engine, the latter can be
used as a standalone unit to deploy on any other platform than Kubernetes, or
as a building block for other use cases.

## Current limitations and planned features

Deployments currently create standalone pods directly (no built-in
Service/Ingress/lifecycle orchestration). It is left to the Kubernetes admin to
set up according to the use cases and internal policies.

Each deployment also creates a dedicated ConfigMap and Secret for the agent
configuration. These resources are not automatically garbage-collected when the
pod is deleted, so they currently need manual cleanup until lifecycle
management is implemented.

Right now, the platform only supports deploying and listing agents. More
management features will be added.

Check out [TODO.md](TODO.md) for more information about planned features and
future work.

## Dev environment setup: Git hooks

This repository includes a pre-commit hook in `.githooks/pre-commit`.

Enable it:

```bash
git config core.hooksPath .githooks
```
