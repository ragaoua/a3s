# cli

To install dependencies:

```bash
bun install
bun run start
```

## Options

Environment variables:

| Var            | Effect                                          | Default   |
| -------------- | ----------------------------------------------- | --------- |
| `PORT`         | Port to listen on.                              | `8000`    |
| `API_KEY`      | API key used to authenticate to the agent.      | _(unset)_ |
| `ACCESS_TOKEN` | Bearer token used to authenticate to the agent. | _(unset)_ |

Generate an `ACCESS_TOKEN` by running the following command against keycloak:

```bash
curl -s -X POST \
    "http://localhost:8080/realms/a3s-realm/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials" \
    -d "client_id=a3s-test-client" \
    -d "client_secret=a3s-test-secret" | jq -r .access_token
```
