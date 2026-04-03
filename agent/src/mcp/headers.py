from google.adk.agents.readonly_context import ReadonlyContext


CUSTOM_METADATA_TEMP_HEADERS_KEY = "temp:headers"


def oauth_token_forward_header_provider(ctx: ReadonlyContext) -> dict[str, str]:
    if ctx.run_config is None or ctx.run_config.custom_metadata is None:
        return {}

    headers = ctx.run_config.custom_metadata[CUSTOM_METADATA_TEMP_HEADERS_KEY]
    if not headers:
        return {}

    return {k: v for k, v in headers.items() if k == "authorization"}
