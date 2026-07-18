"""
The helper handles the wiring that's identical across suites — robust readiness
probe, network/aliases, realm import, OIDC discovery probe — and yields both
the running container and a populated `KeycloakFixture`. Per-suite concerns
(labels, leaked-endpoint bookkeeping, session-failure shutdown skip) stay in
each suite's conftest.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, override

import httpx
from testcontainers.core.network import Network
from testcontainers.keycloak import KeycloakContainer

from tests.common.containers_utilities import poll_until_ready, with_suite_label


# Realm users importable at Keycloak startup, each with password
# "<username>-password" and a user id pinned to the username, so minted tokens
# carry `sub == username`. See tests/common/realm.json.
TestUser = Literal["alice", "bob"]


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

    def mint_user_access_token(self, username: TestUser = "alice") -> str:
        response = httpx.post(
            self.token_endpoint_url,
            data={
                "grant_type": "password",
                "client_id": self.confidential_client_id,
                "client_secret": self.confidential_client_secret,
                "username": username,
                "password": f"{username}-password",
            },
        )
        _ = response.raise_for_status()
        return response.json()["access_token"]


# These must match the values configured in the realm.json fed to Keycloak at
# realm-import time. See tests/common/realm.json.
_KEYCLOAK_CLIENT_ID = "a3s-agent"
_KEYCLOAK_CLIENT_SECRET = "a3s-agent-secret"
_KEYCLOAK_REALM = "a3s-realm"

_KEYCLOAK_REALM_FILE = Path(__file__).parent / "realm.json"

_KEYCLOAK_NETWORK_ALIAS = "keycloak"
KEYCLOAK_INTERNAL_PORT = 8080
_KEYCLOAK_INTERNAL_URL = f"http://{_KEYCLOAK_NETWORK_ALIAS}:{KEYCLOAK_INTERNAL_PORT}"
_KEYCLOAK_ISSUER_INTERNAL = f"{_KEYCLOAK_INTERNAL_URL}/realms/{_KEYCLOAK_REALM}"


class _RobustKeycloakContainer(KeycloakContainer):
    """KeycloakContainer whose readiness probe tolerates the transient 404s
    the management interface serves while it's still wiring up `/health`.

    Upstream's `_readiness_probe` GETs `{management}/health/ready` and calls
    `raise_for_status()` under `@wait_container_is_ready(ConnectionError,
    ReadTimeout)` — so it only retries connection/timeout failures. Keycloak's
    Quarkus management listener starts accepting connections *before* the
    health endpoints are registered, so a probe landing in that window gets a
    404, which surfaces as an `HTTPError` that the decorator doesn't retry and
    fails container startup.
    """

    @override
    def _readiness_probe(self) -> None:
        poll_until_ready(
            f"{self.get_management_url()}/health/ready",
            timeout_seconds=60.0,
            description="Keycloak management health",
        )


def build_keycloak_container(
    *,
    network: Network,
    labels: dict[str, str],
) -> Iterator[tuple[KeycloakContainer, KeycloakFixture]]:
    """Start a labelled Keycloak container on `network`, wait for OIDC discovery
    to return 200, then yield the running container and a populated
    `KeycloakFixture`. Single-shot generator: the caller is responsible for
    stopping the container in its own teardown."""
    container = _RobustKeycloakContainer("quay.io/keycloak/keycloak:26.5.0")
    with_suite_label(container, labels=labels)
    container.with_network(network)
    container.with_network_aliases(_KEYCLOAK_NETWORK_ALIAS)
    # KC_HOSTNAME pins the issuer Keycloak emits so the MCP server (which
    # validates iss) and the agent (which can talk to any URL) agree.
    container.with_env("KC_HOSTNAME", _KEYCLOAK_INTERNAL_URL)
    container.with_env("KC_HOSTNAME_STRICT", "false")
    container.with_env("KC_HTTP_ENABLED", "true")
    container.with_realm_import_file(str(_KEYCLOAK_REALM_FILE))

    container.start()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(KEYCLOAK_INTERNAL_PORT)
    external_base = f"http://{host}:{port}"
    external_issuer = f"{external_base}/realms/{_KEYCLOAK_REALM}"
    discovery_url = f"{external_issuer}/.well-known/openid-configuration"

    poll_until_ready(
        discovery_url, timeout_seconds=60.0, description="Keycloak OIDC discovery"
    )

    yield (
        container,
        KeycloakFixture(
            internal_issuer_url=_KEYCLOAK_ISSUER_INTERNAL,
            token_endpoint_url=f"{external_issuer}/protocol/openid-connect/token",
            external_jwks_url=f"{external_issuer}/protocol/openid-connect/certs",
            external_introspection_url=f"{external_issuer}/protocol/openid-connect/token/introspect",
            confidential_client_id=_KEYCLOAK_CLIENT_ID,
            confidential_client_secret=_KEYCLOAK_CLIENT_SECRET,
        ),
    )
