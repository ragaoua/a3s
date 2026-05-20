from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from keycloak import KeycloakAdmin, KeycloakOpenID
from testcontainers.keycloak import KeycloakContainer

REALM = "a3s-test"
CONFIDENTIAL_CLIENT_ID = "a3s-test-client"
CONFIDENTIAL_CLIENT_SECRET = "a3s-test-secret"
SHORT_LIVED_CLIENT_ID = "a3s-test-short-lived"
SHORT_LIVED_CLIENT_SECRET = "a3s-test-short-lived-secret"
SHORT_LIVED_TOKEN_LIFESPAN_SECONDS = 1


@dataclass(frozen=True)
class KeycloakFixture:
    base_url: str
    realm: str
    issuer_url: str
    jwks_url: str
    confidential_client_id: str
    confidential_client_secret: str

    def mint_access_token(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> str:
        oid = KeycloakOpenID(
            server_url=self.base_url,
            client_id=client_id or self.confidential_client_id,
            realm_name=self.realm,
            client_secret_key=client_secret or self.confidential_client_secret,
        )
        token = oid.token(grant_type="client_credentials")
        return token["access_token"]

    def mint_short_lived_access_token(self) -> str:
        return self.mint_access_token(
            client_id=SHORT_LIVED_CLIENT_ID,
            client_secret=SHORT_LIVED_CLIENT_SECRET,
        )


@pytest.fixture(scope="session")
def keycloak() -> Iterator[KeycloakFixture]:
    with KeycloakContainer(image="quay.io/keycloak/keycloak:26.5.0") as container:
        kc = container.get_client()
        kc.create_realm(
            payload={"realm": REALM, "enabled": True},
            skip_exists=True,
        )
        kc.change_current_realm(REALM)

        _create_confidential_client(
            kc,
            client_id=CONFIDENTIAL_CLIENT_ID,
            secret=CONFIDENTIAL_CLIENT_SECRET,
        )
        _create_confidential_client(
            kc,
            client_id=SHORT_LIVED_CLIENT_ID,
            secret=SHORT_LIVED_CLIENT_SECRET,
            access_token_lifespan_seconds=SHORT_LIVED_TOKEN_LIFESPAN_SECONDS,
        )

        base_url = container.get_url()
        issuer_url = f"{base_url}/realms/{REALM}"

        yield KeycloakFixture(
            base_url=base_url,
            realm=REALM,
            issuer_url=issuer_url,
            jwks_url=f"{issuer_url}/protocol/openid-connect/certs",
            confidential_client_id=CONFIDENTIAL_CLIENT_ID,
            confidential_client_secret=CONFIDENTIAL_CLIENT_SECRET,
        )


def _create_confidential_client(
    kc: KeycloakAdmin,
    *,
    client_id: str,
    secret: str,
    access_token_lifespan_seconds: int | None = None,
) -> None:
    attributes: dict[str, str] = {}
    if access_token_lifespan_seconds is not None:
        attributes["access.token.lifespan"] = str(access_token_lifespan_seconds)

    kc.create_client(
        payload={
            "clientId": client_id,
            "secret": secret,
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "protocol": "openid-connect",
            "attributes": attributes,
        },
        skip_exists=True,
    )
