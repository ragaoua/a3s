from src.auth.context import bind_current_authorization_header
from src.agent.mcp import _oauth_token_forward_header_provider  # pyright: ignore[reportPrivateUsage]


def test_oauth_token_forward_header_provider_returns_empty_dict_when_missing() -> None:
    assert _oauth_token_forward_header_provider() == {}


def test_oauth_token_forward_header_provider_forwards_authorization_header() -> None:
    with bind_current_authorization_header("Bearer test-token"):
        assert _oauth_token_forward_header_provider() == {
            "Authorization": "Bearer test-token"
        }
