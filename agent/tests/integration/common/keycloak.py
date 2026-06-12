from dataclasses import dataclass


@dataclass(frozen=True)
class KeycloakFixture:
    # Internal (container-side) issuer URL — embedded in tokens as the iss
    # claim and used by the MCP server to fetch JWKS / discovery.
    internal_issuer_url: str
    token_endpoint_url: str
    confidential_client_id: str
    confidential_client_secret: str
