from dataclasses import dataclass


@dataclass(frozen=True)
class KeycloakFixture:
    # Internal (container-side) issuer URL — embedded in tokens as the iss
    # claim and used by the MCP server to fetch JWKS / discovery.
    internal_issuer_url: str
    # External URLs — reachable from the host, used by host-side fixtures
    # (e.g. agent inbound auth) that can't resolve the container-network alias.
    token_endpoint_url: str
    external_jwks_url: str
    external_introspection_url: str
    confidential_client_id: str
    confidential_client_secret: str
