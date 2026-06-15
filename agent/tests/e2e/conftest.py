"""Session-scoped infrastructure for the manual e2e suite.

These tests drive the engine through its real `a3s-agent` console entrypoint
against a real LLM endpoint under OAuth2 inbound auth. They are gated behind
the `e2e` pytest marker (opt in with `-m e2e`) and the `A3S_LLM_*` env vars;
if any of the env vars are missing, every test in the suite skips.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from testcontainers.core.network import Network

from tests.common.containers_utilities import reap_leaked_containers
from tests.common.keycloak import KeycloakFixture, build_keycloak_container

_CONTAINER_LABEL_KEY = "a3s-agent-e2e-suite"
_CONTAINER_LABEL_VALUE = "1"
_CONTAINER_LABEL_FILTER = f"{_CONTAINER_LABEL_KEY}={_CONTAINER_LABEL_VALUE}"

_LLM_ENV_VAR_NAMES = ("A3S_LLM_API_URL", "A3S_LLM_API_KEY", "A3S_LLM_MODEL")


@pytest.fixture(scope="session")
def e2e_llm_env() -> dict[str, str]:
    """Read + validate A3S_LLM_API_URL / A3S_LLM_API_KEY / A3S_LLM_MODEL.

    Skips every dependent test if any of the three are unset — these are the
    env-var substitutions exercised end-to-end by the e2e YAML config.
    """
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in _LLM_ENV_VAR_NAMES:
        value = os.environ.get(name, "").strip()
        if not value:
            missing.append(name)
        else:
            values[name] = value

    if missing:
        pytest.skip(
            "e2e tests require these env vars to be set against a real LLM: "
            + ", ".join(missing)
        )
    return values


@pytest.fixture(scope="session")
def _e2e_network() -> Iterator[Network]:  # pyright: ignore[reportUnusedFunction]
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
