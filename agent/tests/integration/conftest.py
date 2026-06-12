"""Session-scoped integration test infrastructure.

Spins up real Keycloak + MCP-server containers on a shared docker network,
gates readiness on OIDC discovery, labels everything so leaked containers
from a killed previous run get reaped at next start, and on test failure
dumps container logs into the report while keeping the failed containers
alive for manual inspection.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import override

import docker
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.keycloak import KeycloakContainer

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth
from tests.integration.common.containers_utilities import (
    build_image,
    poll_until_ready,
    reap_leaked_containers,
    wait_for_port,
    with_suite_label,
)
from tests.integration.common.keycloak import KeycloakFixture
from tests.integration.common.mcp import McpServerFixture
from tests.integration.common.subagent import SubagentServerFixture

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

# Every container the suite spins up gets tagged with this label, and at
# session start we kill anything still alive matching it from a previous run.
# That way a leaked session (Ctrl-C, SIGKILL, CI cancellation) gets reaped
# at the start of the next session with no manual cleanup.
_CONTAINER_LABEL_KEY = "a3s-agent-integration-suite"
_CONTAINER_LABEL_VALUE = "1"
_CONTAINER_LABEL_FILTER = f"{_CONTAINER_LABEL_KEY}={_CONTAINER_LABEL_VALUE}"


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
            timeout_seconds=20.0,
            description="Keycloak management health",
        )


_KEYCLOAK_CLIENT_ID = (
    "a3s-agent"  # This needs to correspond to the client id configured in the keycloak
)


_KEYCLOAK_CLIENT_SECRET = "a3s-agent-secret"  # This needs to correspond to the client secret configured in the keycloak

_KEYCLOAK_REALM = "a3s-realm"
_KEYCLOAK_NETWORK_ALIAS = "keycloak"
_KEYCLOAK_INTERNAL_PORT = 8080
_KEYCLOAK_INTERNAL_URL = f"http://{_KEYCLOAK_NETWORK_ALIAS}:{_KEYCLOAK_INTERNAL_PORT}"
_KEYCLOAK_ISSUER_INTERNAL = f"{_KEYCLOAK_INTERNAL_URL}/realms/{_KEYCLOAK_REALM}"

_MCP_NETWORK_ALIAS = "mcp"
_MCP_INTERNAL_PORT = 3000
_MCP_AUDIENCE = (
    "a3s-mcp"  # This needs to correspond to the audience configured in the keycloak
)
_MCP_IMAGE_TAG = "a3s-agent-test-mcp:latest"

_SUBAGENT_NETWORK_ALIAS = "subagent"
_SUBAGENT_INTERNAL_PORT = 3000
_SUBAGENT_AUDIENCE = "a3s-subagent"  # This needs to correspond to the audience configured in the keycloak
_SUBAGENT_IMAGE_TAG = "a3s-agent-test-subagent:latest"
_SUBAGENT_RESPONSE_TEXT = "Subagent acknowledged the request."

_CONTAINERS_DIR = Path(__file__).parent / "containers"
_KEYCLOAK_REALM_FILE = _CONTAINERS_DIR / "keycloak" / "realm.json"
_MCP_IMAGE_CONTEXT = _CONTAINERS_DIR / "mcp_server"
_SUBAGENT_IMAGE_CONTEXT = _CONTAINERS_DIR / "subagent_server"


# ----------------------------------------------------------------------------
# Failure tracking (shared between makereport hook and fixture teardown)
# ----------------------------------------------------------------------------


class _SessionState:
    """Mutable session-level state shared across hooks and fixtures."""

    has_failures: bool = False
    leaked_endpoint_details: list[str] = []


_session_state = _SessionState()


def _record_leaked_endpoint(label: str, url: str) -> None:
    _session_state.leaked_endpoint_details.append(f"{label}: {url}")


# ----------------------------------------------------------------------------
# Pytest hooks
# ----------------------------------------------------------------------------


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()  # pyright: ignore[reportAny]

    # Setup failures (e.g. a container failing to come up) count too: we
    # want to preserve whatever state did make it up so the developer can
    # poke at it.
    if report.failed and report.when in ("setup", "call"):
        _session_state.has_failures = True
        _dump_container_logs_into_report(report)


def _dump_container_logs_into_report(report: pytest.TestReport) -> None:
    """Append docker logs of every suite-labelled container to the report."""
    try:
        client = docker.from_env()
    except Exception:
        return

    sections: list[str] = []
    for container in client.containers.list(
        all=True, filters={"label": _CONTAINER_LABEL_FILTER}
    ):
        try:
            stdout = container.logs(stdout=True, stderr=False).decode(  # pyright: ignore[reportUnknownMemberType]
                "utf-8", errors="replace"
            )
            stderr = container.logs(stdout=False, stderr=True).decode(  # pyright: ignore[reportUnknownMemberType]
                "utf-8", errors="replace"
            )
        except Exception as exc:  # pragma: no cover - best-effort dump
            sections.append(
                f"--- container {container.name} ({container.image.tags}): failed to read logs: {exc} ---"
            )
            continue
        sections.append(
            f"--- container {container.name} ({container.image.tags}) stdout ---\n{stdout}"
        )
        sections.append(
            f"--- container {container.name} ({container.image.tags}) stderr ---\n{stderr}"
        )

    if sections:
        report.sections.append(("integration container logs", "\n".join(sections)))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _session_state.has_failures and _session_state.leaked_endpoint_details:
        terminalreporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminalreporter is not None:
            terminalreporter.write_sep("=", "leaked integration containers")  # pyright: ignore[reportAny]
            terminalreporter.write_line(
                "session failed; the following containers were kept alive for inspection"
                " and will be reaped at the start of the next session:"
            )
            for line in _session_state.leaked_endpoint_details:
                terminalreporter.write_line(f"  {line}")


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _integration_network() -> Iterator[Network]:  # pyright: ignore[reportUnusedFunction]
    reap_leaked_containers(label=_CONTAINER_LABEL_FILTER)
    network = Network(
        docker_network_kw={"labels": {_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE}}
    )
    network.create()
    try:
        yield network
    finally:
        if not _session_state.has_failures:
            network.remove()


@pytest.fixture(scope="session")
def keycloak(_integration_network: Network) -> Iterator[KeycloakFixture]:
    container = _RobustKeycloakContainer()
    with_suite_label(container, labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE})
    container.with_network(_integration_network)
    container.with_network_aliases(_KEYCLOAK_NETWORK_ALIAS)
    # KC_HOSTNAME pins the issuer Keycloak emits so the MCP server (which
    # validates iss) and the agent (which can talk to any URL) agree.
    container.with_env("KC_HOSTNAME", _KEYCLOAK_INTERNAL_URL)
    container.with_env("KC_HOSTNAME_STRICT", "false")
    container.with_env("KC_HTTP_ENABLED", "true")
    container.with_realm_import_file(str(_KEYCLOAK_REALM_FILE))

    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(_KEYCLOAK_INTERNAL_PORT)
        external_base = f"http://{host}:{port}"
        external_issuer = f"{external_base}/realms/{_KEYCLOAK_REALM}"
        discovery_url = f"{external_issuer}/.well-known/openid-configuration"

        poll_until_ready(
            discovery_url, timeout_seconds=120.0, description="Keycloak OIDC discovery"
        )

        _record_leaked_endpoint("Keycloak (external)", external_base)

        yield KeycloakFixture(
            internal_issuer_url=_KEYCLOAK_ISSUER_INTERNAL,
            token_endpoint_url=f"{external_issuer}/protocol/openid-connect/token",
            confidential_client_id=_KEYCLOAK_CLIENT_ID,
            confidential_client_secret=_KEYCLOAK_CLIENT_SECRET,
        )
    finally:
        if not _session_state.has_failures:
            container.stop()


@pytest.fixture(scope="session")
def mcp_server(
    keycloak: KeycloakFixture,
    _integration_network: Network,
) -> Iterator[McpServerFixture]:
    build_image(
        context_dir=_MCP_IMAGE_CONTEXT,
        tag=_MCP_IMAGE_TAG,
        labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE},
    )

    container = DockerContainer(_MCP_IMAGE_TAG)
    with_suite_label(container, labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE})
    container.with_network(_integration_network)
    container.with_network_aliases(_MCP_NETWORK_ALIAS)
    container.with_exposed_ports(_MCP_INTERNAL_PORT)
    container.with_env("ISSUER", keycloak.internal_issuer_url)
    container.with_env("AUDIENCE", _MCP_AUDIENCE)
    container.with_env(
        "JWKS_URI", f"{keycloak.internal_issuer_url}/protocol/openid-connect/certs"
    )
    container.with_env(
        "RESOURCE_SERVER_URL",
        f"http://{_MCP_NETWORK_ALIAS}:{_MCP_INTERNAL_PORT}/",
    )
    container.with_env("PORT", str(_MCP_INTERNAL_PORT))
    container.with_env("HOST", "0.0.0.0")

    container.start()
    try:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(_MCP_INTERNAL_PORT))
        wait_for_port(host, port, timeout_seconds=60.0)

        external_url = f"http://{host}:{port}/mcp"
        _record_leaked_endpoint("MCP server (external)", external_url)

        yield McpServerFixture(url=external_url)
    finally:
        if not _session_state.has_failures:
            container.stop()


@pytest.fixture(scope="session")
def subagent_server(
    keycloak: KeycloakFixture,
    _integration_network: Network,
) -> Iterator[SubagentServerFixture]:
    build_image(
        context_dir=_SUBAGENT_IMAGE_CONTEXT,
        tag=_SUBAGENT_IMAGE_TAG,
        labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE},
    )

    # The subagent embeds its own URL in the AgentCard. Pointing it at the
    # in-network alias is fine — the parent agent only reaches it from the
    # host side, but it dereferences the URL in the card to issue requests,
    # so a network-internal address would break the client. We pre-bind a
    # host port and feed it back in via PUBLIC_URL.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        host_port: int = s.getsockname()[1]

    container = DockerContainer(_SUBAGENT_IMAGE_TAG)
    with_suite_label(container, labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE})
    container.with_network(_integration_network)
    container.with_network_aliases(_SUBAGENT_NETWORK_ALIAS)
    container.with_bind_ports(_SUBAGENT_INTERNAL_PORT, host_port)
    container.with_env("ISSUER", keycloak.internal_issuer_url)
    container.with_env("AUDIENCE", _SUBAGENT_AUDIENCE)
    container.with_env(
        "JWKS_URI", f"{keycloak.internal_issuer_url}/protocol/openid-connect/certs"
    )
    container.with_env("PORT", str(_SUBAGENT_INTERNAL_PORT))
    container.with_env("HOST", "0.0.0.0")
    container.with_env("PUBLIC_URL", f"http://127.0.0.1:{host_port}")
    container.with_env("RESPONSE_TEXT", _SUBAGENT_RESPONSE_TEXT)

    container.start()
    try:
        # Poll the agent card endpoint, not just port-open: with `with_bind_ports`
        # Podman's userland proxy starts listening on the host port immediately,
        # before the container's Python process is up. A port-open check would
        # race and pass too early.
        external_url = f"http://127.0.0.1:{host_port}"
        poll_until_ready(
            f"{external_url}/.well-known/agent-card.json",
            timeout_seconds=60.0,
            description="subagent agent card",
        )

        _record_leaked_endpoint("Subagent server (external)", external_url)

        yield SubagentServerFixture(url=external_url)
    finally:
        if not _session_state.has_failures:
            container.stop()


@pytest.fixture(autouse=True)
def _clear_outbound_client_credentials_cache() -> Iterator[None]:
    # OAuthClientCredentialsAuth keeps a class-level token cache keyed by
    # (token_endpoint, client_id). The keycloak fixture is session-scoped,
    # so consecutive tests would otherwise hit the cache and skip the
    # token-endpoint round trip we're trying to exercise.
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE.clear()  # pyright: ignore[reportPrivateUsage]
    OAuthClientCredentialsAuth._ACCESS_TOKEN_CACHE_LOCKS.clear()  # pyright: ignore[reportPrivateUsage]
    yield
