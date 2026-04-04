from google.adk.agents.readonly_context import ReadonlyContext


CUSTOM_METADATA_AUTH_HEADER_KEY = "temp:authorization_header"


def oauth_token_forward_header_provider(ctx: ReadonlyContext) -> dict[str, str]:
    if ctx.run_config is None or ctx.run_config.custom_metadata is None:
        return {}

    authorization_header = ctx.run_config.custom_metadata.get(
        CUSTOM_METADATA_AUTH_HEADER_KEY
    )
    if not authorization_header:
        return {}

    return {"Authorization": authorization_header}
