"""Session-scoped integration test infrastructure.

Spins up real Keycloak + MCP-server containers on a shared docker network,
gates readiness on OIDC discovery, labels everything so leaked containers
from a killed previous run get reaped at next start, and on test failure
dumps container logs into the report while keeping the failed containers
alive for manual inspection.
"""

from __future__ import annotations

import io
import socket
import tarfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import docker
import httpx
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.keycloak import KeycloakContainer

from src.auth.outbound.oauth_client_credentials import OAuthClientCredentialsAuth

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

_KEYCLOAK_REALM = "a3s-realm"
_KEYCLOAK_NETWORK_ALIAS = "keycloak"
_KEYCLOAK_INTERNAL_PORT = 8080
_KEYCLOAK_INTERNAL_URL = f"http://{_KEYCLOAK_NETWORK_ALIAS}:{_KEYCLOAK_INTERNAL_PORT}"
_KEYCLOAK_ISSUER_INTERNAL = f"{_KEYCLOAK_INTERNAL_URL}/realms/{_KEYCLOAK_REALM}"

_MCP_NETWORK_ALIAS = "mcp"
_MCP_INTERNAL_PORT = 3000
_MCP_AUDIENCE = "a3s-mcp"
_MCP_IMAGE_TAG = "a3s-agent-test-mcp:latest"

_CONTAINERS_DIR = Path(__file__).parent / "containers"
_KEYCLOAK_REALM_FILE = _CONTAINERS_DIR / "keycloak" / "realm.json"
_MCP_IMAGE_CONTEXT = _CONTAINERS_DIR / "mcp_server"


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
# Container utilities
# ----------------------------------------------------------------------------


def _build_image(*, context_dir: Path, tag: str) -> None:
    """Build a docker image from `context_dir`.

    Streams the build context as a tar with ownership normalised to 0:0 —
    rootless podman can't map the host user's UID/GID into the build
    container's namespace (the host UID falls outside the configured
    subuid/subgid range), and an unnormalised context blows up with a
    `lchown invalid argument` error during the build.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for entry in sorted(context_dir.rglob("*")):
            if not entry.is_file():
                continue
            arcname = str(entry.relative_to(context_dir))
            info = tar.gettarinfo(str(entry), arcname=arcname)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            with entry.open("rb") as fp:
                tar.addfile(info, fp)
    buffer.seek(0)

    client = docker.from_env()
    stream = client.api.build(  # pyright: ignore[reportUnknownMemberType]
        fileobj=buffer,
        custom_context=True,
        tag=tag,
        rm=True,
        decode=True,
        labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE},
    )
    for chunk in stream:
        if "error" in chunk:
            raise RuntimeError(f"image build failed for {tag}: {chunk['error']}")


def _reap_leaked_containers() -> None:
    """Kill any containers left over from a previous run of the suite."""
    client = docker.from_env()
    for container in client.containers.list(
        all=True, filters={"label": _CONTAINER_LABEL_FILTER}
    ):
        try:
            container.remove(force=True)
        except Exception:
            pass


def _with_suite_label(container: DockerContainer) -> DockerContainer:
    return container.with_kwargs(labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE})


def _poll_until_ready(
    url: str,
    *,
    timeout_seconds: float,
    description: str,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                return
            last_error = RuntimeError(f"GET {url} returned {response.status_code}")
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1.0)
    raise TimeoutError(
        f"{description} not ready at {url} after {timeout_seconds:.0f}s"
    ) from last_error


def _wait_for_port(host: str, port: int, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.5)
    raise TimeoutError(
        f"{host}:{port} did not start accepting connections within {timeout_seconds:.0f}s"
    ) from last_error


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _integration_network() -> Iterator[Network]:  # pyright: ignore[reportUnusedFunction]
    _reap_leaked_containers()
    network = Network(
        docker_network_kw={"labels": {_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE}}
    )
    network.create()
    try:
        yield network
    finally:
        if not _session_state.has_failures:
            network.remove()


@dataclass(frozen=True)
class KeycloakFixture:
    realm: str
    # External (host-side) issuer URL — used by the agent to fetch tokens.
    external_issuer_url: str
    # Internal (container-side) issuer URL — embedded in tokens as the iss
    # claim and used by the MCP server to fetch JWKS / discovery.
    internal_issuer_url: str
    token_endpoint_url: str
    confidential_client_id: str
    confidential_client_secret: str


@pytest.fixture(scope="session")
def keycloak(_integration_network: Network) -> Iterator[KeycloakFixture]:
    container = KeycloakContainer()
    _with_suite_label(container)
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

        _poll_until_ready(
            discovery_url, timeout_seconds=120.0, description="Keycloak OIDC discovery"
        )

        _record_leaked_endpoint("Keycloak (external)", external_base)

        yield KeycloakFixture(
            realm=_KEYCLOAK_REALM,
            external_issuer_url=external_issuer,
            internal_issuer_url=_KEYCLOAK_ISSUER_INTERNAL,
            token_endpoint_url=f"{external_issuer}/protocol/openid-connect/token",
            confidential_client_id="a3s-agent",
            confidential_client_secret="a3s-agent-secret",
        )
    finally:
        if not _session_state.has_failures:
            container.stop()


@dataclass(frozen=True)
class McpServerFixture:
    # URL the agent uses to reach the MCP server (host-side).
    external_url: str
    audience: str


@pytest.fixture(scope="session")
def mcp_server(
    keycloak: KeycloakFixture, _integration_network: Network
) -> Iterator[McpServerFixture]:
    _build_image(
        context_dir=_MCP_IMAGE_CONTEXT,
        tag=_MCP_IMAGE_TAG,
    )

    container = DockerContainer(_MCP_IMAGE_TAG)
    _with_suite_label(container)
    container.with_network(_integration_network)
    container.with_network_aliases(_MCP_NETWORK_ALIAS)
    container.with_exposed_ports(_MCP_INTERNAL_PORT)
    container.with_env("ISSUER", keycloak.internal_issuer_url)
    container.with_env("AUDIENCE", _MCP_AUDIENCE)
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
        _wait_for_port(host, port, timeout_seconds=60.0)

        external_url = f"http://{host}:{port}/mcp"
        _record_leaked_endpoint("MCP server (external)", external_url)

        yield McpServerFixture(external_url=external_url, audience=_MCP_AUDIENCE)
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
