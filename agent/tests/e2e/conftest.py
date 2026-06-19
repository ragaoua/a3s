"""Session-scoped infrastructure for the manual e2e suite.

These tests drive the engine through its real `a3s-agent` console entrypoint
against a real LLM endpoint under OAuth2 inbound auth. They are gated behind
the `e2e` pytest marker (opt in with `-m e2e`) and the `A3S_LLM_*` env vars.

The local-subprocess test and the containerised test live in different network
topologies, so they each have their own LLM URL env var — `A3S_LLM_API_URL`
must be reachable from the host, `A3S_LLM_API_URL_CONTAINER` must be reachable
from inside the docker network the agent container joins. The other two env
vars (key, model) are shared. Each test skips independently when its own URL
is missing, so setting only one runs only the matching test.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from pathlib import Path
import subprocess

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

from tests.common.containers_utilities import (
    build_image,
    poll_until_ready,
    reap_leaked_containers,
    with_suite_label,
)
from tests.common.keycloak import KeycloakFixture, build_keycloak_container
from tests.e2e.utils import (
    PROJECT_DIR,
    LocalAgent,
    LocalAgentInContainer,
    make_agent_config,
)

_CONTAINER_LABEL_KEY = "a3s-agent-e2e-suite"
_CONTAINER_LABEL_VALUE = "1"
_CONTAINER_LABEL_FILTER = f"{_CONTAINER_LABEL_KEY}={_CONTAINER_LABEL_VALUE}"

_LOCAL_LLM_API_URL_ENV_VAR = "A3S_LLM_API_URL"
_CONTAINER_LLM_API_URL_ENV_VAR = "A3S_LLM_API_URL_CONTAINER"
_LLM_API_KEY_ENV_VAR = "A3S_LLM_API_KEY"
_LLM_MODEL_ENV_VAR = "A3S_LLM_MODEL"

_AGENT_IMAGE_TAG = "a3s-agent-e2e:latest"


def _is_env_var_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Skip e2e items at collection time when their required LLM env vars are
    missing — per-test granular based on whether the item uses `local_agent`
    or `local_agent_in_container`.

    Done at collection time so the skip fires before pytest resolves any
    session-scoped fixtures, in particular the docker-touching keycloak /
    `_e2e_network` ones. Pure fixture-level skips would still bring those up
    even when the test will skip, because session-scoped fixtures resolve
    before function-scoped ones in a test's setup chain.
    """
    for item in items:
        if "e2e" not in item.keywords:
            continue
        fixtures = getattr(item, "fixturenames", ())
        needs_local = "local_agent" in fixtures
        needs_container = "local_agent_in_container" in fixtures
        if not (needs_local or needs_container):
            continue

        missing: list[str] = []
        if needs_local and not _is_env_var_set(_LOCAL_LLM_API_URL_ENV_VAR):
            missing.append(_LOCAL_LLM_API_URL_ENV_VAR)
        if needs_container and not _is_env_var_set(_CONTAINER_LLM_API_URL_ENV_VAR):
            missing.append(_CONTAINER_LLM_API_URL_ENV_VAR)
        for shared in (_LLM_API_KEY_ENV_VAR, _LLM_MODEL_ENV_VAR):
            if not _is_env_var_set(shared):
                missing.append(shared)

        if missing:
            item.add_marker(
                pytest.mark.skip(
                    reason="this e2e test requires these env vars to be set: "
                    + ", ".join(missing)
                )
            )


def _read_llm_env(api_url_env_var: str) -> dict[str, str]:
    """Return the three LLM env vars keyed by the canonical
    `A3S_LLM_API_URL` / `A3S_LLM_API_KEY` / `A3S_LLM_MODEL` names — that's
    what the YAML's `${A3S_LLM_API_URL}` substitution looks for regardless
    of which URL var the caller read from.

    Presence is enforced at collection time by `pytest_collection_modifyitems`.
    """
    return {
        _LOCAL_LLM_API_URL_ENV_VAR: os.environ[api_url_env_var],
        _LLM_API_KEY_ENV_VAR: os.environ[_LLM_API_KEY_ENV_VAR],
        _LLM_MODEL_ENV_VAR: os.environ[_LLM_MODEL_ENV_VAR],
    }


@pytest.fixture(scope="session")
def _local_llm_env() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
    """LLM env for the host-side subprocess. `A3S_LLM_API_URL` must be
    reachable from the host."""
    return _read_llm_env(_LOCAL_LLM_API_URL_ENV_VAR)


@pytest.fixture(scope="session")
def _container_llm_env() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
    """LLM env for the agent container. `A3S_LLM_API_URL_CONTAINER` must be
    reachable from inside the e2e docker network."""
    return _read_llm_env(_CONTAINER_LLM_API_URL_ENV_VAR)


@pytest.fixture(scope="session")
def _e2e_network() -> Iterator[Network]:
    """Docker network the e2e suite's Keycloak runs on.

    Labelled so leaked containers from a killed run get reaped at the start
    of the next session. No leaked-endpoint bookkeeping — the integration
    suite needs that to preserve failed-state for inspection, but e2e is
    cheap to rerun manually.
    """
    reap_leaked_containers(label=_CONTAINER_LABEL_FILTER)

    network = Network(
        docker_network_kw={"labels": {_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE}}
    )

    try:
        yield network.create()
    finally:
        network.remove()


@pytest.fixture(scope="session")
def keycloak(_e2e_network: Network) -> Iterator[KeycloakFixture]:
    container, fixture = next(
        build_keycloak_container(
            network=_e2e_network,
            labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE},
        )
    )
    try:
        yield fixture
    finally:
        container.stop()


@pytest.fixture
def local_agent(
    _local_llm_env: dict[str, str],
    tmp_path: Path,
    keycloak: KeycloakFixture,
) -> Iterator[LocalAgent]:
    """Spawn the real `a3s-agent` console script against a real LLM under
    OAuth2 inbound auth, do an A2A round trip, then shut the server down via
    the stdin `"q"` quit path and assert it exits cleanly."""
    listen_address = "127.0.0.1"
    with socket.socket() as s:
        s.bind((listen_address, 0))
        port: int = s.getsockname()[1]

    config_path = make_agent_config(
        path=tmp_path,
        listen_address=listen_address,
        listen_port=port,
        issuer_url=keycloak.internal_issuer_url,
        jwks_url=keycloak.external_jwks_url,
    )
    base_url = f"http://{listen_address}:{port}"

    env = {
        **os.environ,
        **_local_llm_env,
        "A3S_CONFIG_FILE": str(config_path),
    }

    proc = subprocess.Popen(
        ["uv", "run", "a3s-agent"],
        cwd=str(PROJECT_DIR),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    poll_until_ready(
        f"{base_url}/.well-known/agent-card.json",
        timeout_seconds=30.0,
        description="agent card",
    )

    yield LocalAgent(base_url=base_url, proc=proc)


@pytest.fixture
def local_agent_in_container(
    _e2e_network: Network,
    _container_llm_env: dict[str, str],
    keycloak: KeycloakFixture,
    tmp_path: Path,
) -> Iterator[LocalAgentInContainer]:
    """Run the agent image on the e2e docker network with OAuth2 inbound
    auth pointing at the suite Keycloak, and wait for its agent card before
    yielding. Container is torn down at end-of-test."""
    # Pre-bind a host port and use it as the container's listen port too:
    # the agent inside the container binds 0.0.0.0:port and the host port
    # maps to the same number, so the YAML and host-side requests agree.
    build_image(
        context_dir=PROJECT_DIR,
        tag=_AGENT_IMAGE_TAG,
        labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE},
    )

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]

    config_path = make_agent_config(
        path=tmp_path,
        listen_address="0.0.0.0",
        listen_port=port,
        issuer_url=keycloak.internal_issuer_url,
        jwks_url=f"{keycloak.internal_issuer_url}/protocol/openid-connect/certs",
    )

    container = DockerContainer(_AGENT_IMAGE_TAG)
    with_suite_label(container, labels={_CONTAINER_LABEL_KEY: _CONTAINER_LABEL_VALUE})
    container.with_network(_e2e_network)
    container.with_bind_ports(port, port)
    container.with_volume_mapping(str(config_path), "/app/config/agent.yaml", mode="ro")
    for name, value in _container_llm_env.items():
        container.with_env(name, value)

    container.start()
    try:
        base_url = f"http://127.0.0.1:{port}"
        poll_until_ready(
            f"{base_url}/.well-known/agent-card.json",
            timeout_seconds=60.0,
            description="containerised agent card",
        )
        yield LocalAgentInContainer(base_url=base_url, container=container)
    finally:
        container.stop()
