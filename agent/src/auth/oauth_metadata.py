from authlib.oauth2.rfc8414 import AuthorizationServerMetadata, get_well_known_url
from pydantic import JsonValue
from returns.result import Failure, Result, Success

from src.utils import FetchJson


async def fetch_authorization_server_metadata(
    issuer_url: str,
    *,
    fetch_json: FetchJson,
) -> Result[AuthorizationServerMetadata, str]:
    """Fetch and validate an OAuth2 authorization server's RFC 8414 metadata.

    Builds the issuer's ``.well-known`` URL, fetches the metadata document, and
    validates it (see :func:`validate_authorization_server_metadata`).
    ``issuer_url`` must already be normalized (no trailing slash).
    """
    try:
        metadata_url = get_well_known_url(issuer_url, external=True)
        metadata_raw = await fetch_json(metadata_url)
    except Exception as err:
        return Failure(f"Failed to fetch authorization server metadata: {err}")

    return validate_authorization_server_metadata(
        metadata_raw,
        expected_issuer=issuer_url,
    )


def validate_authorization_server_metadata(
    metadata_raw: dict[str, JsonValue],
    *,
    expected_issuer: str,
) -> Result[AuthorizationServerMetadata, str]:
    """Validate an RFC 8414 metadata document and confirm its issuer.

    Constructs ``AuthorizationServerMetadata``, runs its issuer validation, and
    verifies the advertised ``issuer`` matches ``expected_issuer`` (trailing
    slash ignored).
    """
    try:
        metadata = AuthorizationServerMetadata(metadata_raw)
        metadata.validate_issuer()
    except Exception as err:
        return Failure(f"Failed to validate authorization server metadata: {err}")

    metadata_issuer = str(metadata.get("issuer", "")).rstrip("/")
    if metadata_issuer != expected_issuer:
        return Failure(
            "Failed to validate authorization server metadata: "
            + "Issuer mismatch in OAuth2 authorization server metadata"
        )

    return Success(metadata)
