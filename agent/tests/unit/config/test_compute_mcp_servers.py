import pytest

from src.config import compute_mcp_servers


def test_compute_mcp_servers_returns_empty_when_env_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_SERVERS", raising=False)

    assert compute_mcp_servers() == []


def test_compute_mcp_servers_returns_empty_when_env_is_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVERS", "   ")

    assert compute_mcp_servers() == []


def test_compute_mcp_servers_parses_and_trims_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVERS", "  https://a.example , , https://b.example  ")

    assert compute_mcp_servers() == ["https://a.example", "https://b.example"]


def test_compute_mcp_servers_preserves_order_and_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVERS", "mcp://one,mcp://two,mcp://one")

    assert compute_mcp_servers() == ["mcp://one", "mcp://two", "mcp://one"]


def test_compute_mcp_servers_trims_newline_and_tab_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVERS", "\n mcp://one\t,\tmcp://two \n")

    assert compute_mcp_servers() == ["mcp://one", "mcp://two"]


def test_compute_mcp_servers_returns_empty_for_only_commas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVERS", ",,,")

    assert compute_mcp_servers() == []


def test_compute_mcp_servers_preserves_internal_spaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SERVERS", "mcp://server with space, mcp://other")

    assert compute_mcp_servers() == ["mcp://server with space", "mcp://other"]
