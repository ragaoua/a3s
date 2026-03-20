Create a local Kind cluster:

```bash
KIND_EXPERIMENTAL_PROVIDER=podman kind create --config kind.yaml
```

Load the agent image (see [../agent/README.md](../agent/README.md) ) into Kind:

```bash
KIND_EXPERIMENTAL_PROVIDER=podman kind load image-archive --name a3s-kind <(podman save localhost/a3s-agent --format oci-archive)
KIND_EXPERIMENTAL_PROVIDER=podman kind load image-archive --name a3s-kind <(podman save localhost/a3s-app --format oci-archive)
# NOTE: `KIND_EXPERIMENTAL_PROVIDER=podman kind load docker-image agent --name a3s-kind`
# doesn't work. It seems to be a known issue with loading podman images in kind, for which
# the above is a workaround (see https://github.com/kubernetes-sigs/kind/issues/2038).
```

Create a service account, with the role and role bindings to create pods:

```bash
kubectl apply \
    -f app-ns.yaml \
    -f agents-ns.yaml \
    -f sa.yaml \
    -f role.yaml \
    -f role_binding.yaml
```

Deploy the app:

```bash
kubectl run app \
    --image=localhost/a3s-app \
    --namespace app-ns \
    --image-pull-policy=Never \
    --restart=Never \
    --overrides='{"apiVersion":"v1","spec":{"serviceAccountName":"app-sa"}}' \
    --env K8S_NAMESPACE=agents-ns \
    --env ORIGIN=http://localhost:8080 \
    --env NODE_TLS_REJECT_UNAUTHORIZED=0
kubectl expose pod app \
    --name app-svc \
    --namespace app-ns \
    --type=NodePort \
    --port=3000 \
    --target-port=3000 \
    --overrides='{"apiVersion":"v1","spec":{"ports":[{"port":3000,"targetPort":3000,"protocol":"TCP","nodePort":30080}]}}'
```

**Note 1**: nodePort 30080 must be the same as declared in the
[kind.yaml](kind.yaml) file.

**Note 2**: as for port 3000, it must be the same as the port the app is
running on, inside the container. See
[../../app/Dockerfile](../../app/Dockerfile).

**Note 3**: again, mapping between nodePort 30080 et hostPort 8080 is set in
the `kind.yaml` file (so the ORIGIN must also be that exact port. By default,
it's port http://localhost:3000, same port as the container port).

Then access the app on localhost:8080.
