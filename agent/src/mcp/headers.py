from google.adk.agents.readonly_context import ReadonlyContext

from src.auth.context import get_current_authorization_header


def oauth_token_forward_header_provider(_: ReadonlyContext) -> dict[str, str]:
    authorization_header = get_current_authorization_header()
    if not authorization_header:
        return {}

    return {"Authorization": authorization_header}
