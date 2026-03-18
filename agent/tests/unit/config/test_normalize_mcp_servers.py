import pytest

from src.config import normalize_mcp_servers


@pytest.mark.parametrize(
    "value",
    ["", "   "],
)
def test_compute_mcp_servers_returns_empty_when_value_is_blank(
    value: str,
) -> None:
    assert normalize_mcp_servers(value) == []


def test_compute_mcp_servers_returns_empty_when_value_is_missing() -> None:
    assert normalize_mcp_servers(None) == []


def test_compute_mcp_servers_parses_and_trims_values() -> None:

    assert normalize_mcp_servers("  https://a.example , , https://b.example  ") == [
        "https://a.example",
        "https://b.example",
    ]


def test_compute_mcp_servers_preserves_order_and_duplicates() -> None:
    assert normalize_mcp_servers("mcp://one,mcp://two,mcp://one") == [
        "mcp://one",
        "mcp://two",
        "mcp://one",
    ]


def test_compute_mcp_servers_trims_newline_and_tab_whitespace() -> None:

    assert normalize_mcp_servers("\n mcp://one\t,\tmcp://two \n") == [
        "mcp://one",
        "mcp://two",
    ]


def test_compute_mcp_servers_returns_empty_for_only_commas() -> None:
    assert normalize_mcp_servers(",,,") == []


def test_compute_mcp_servers_preserves_internal_spaces() -> None:
    assert normalize_mcp_servers("mcp://server with space, mcp://other") == [
        "mcp://server with space",
        "mcp://other",
    ]
