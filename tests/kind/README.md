# Running the app

## Option 1: Configure a kind cluster, then deploy the app on the cluster

k

```bash
./deploy_app_in_kind.sh
```

App should be accessible at `localhost:8080`.

## Option 2: Configure a kind cluster, then run the app outside the cluster

```bash
./configure_kind_cluster_and_deploy_app.sh
```

App should be accessible at `localhost:3000`.

# Accessing the deployed agents

After creating an agent, create a NodePort service to access it outside the
cluster:

```bash
agent_name=...
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: agent-svc
  namespace: agents-ns
spec:
  type: NodePort
  selector:
    run: agent
    name: ${agent_name}
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
      nodePort: 30081
EOF
```

Here :

- `agent_name` is the name of the agent as specified in the app's form while
  deploying ;
- 8000 is the internal port on which the agent is running inside its pod ;
- 30081 is the port that's configured in [kind.yaml](kind.yaml) to be mapped to
  kind's host's 8000 port.
