"""Noxus integration credentials for an Athom Homey."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from noxus_sdk.errors import IntegrationFailedError
from noxus_sdk.integrations import (
    BaseCredentials,
    BaseIntegration,
    IntegrationProviderDefinition,
    OAuth2ProviderDefinition,
    OAuth2TokenResponseDefinition,
)
from noxus_sdk.ncl import (
    ConfigNumber,
    ConfigPassword,
    ConfigText,
    ConfigToggle,
    Parameter,
)

from homey.client import HomeyClient, normalize_base_url

if TYPE_CHECKING:
    from noxus_sdk.plugins.context import RemoteExecutionContext


HOMEY_IMAGE_URL = "https://etc.athom.com/logo/transparent/128.png"


class HomeyCredentials(BaseCredentials):
    type: ClassVar[str] = "homey"

    address: str = Parameter(
        default="",
        description="The Homey URL used with a Homey Pro 2023+ personal API key.",
        display=ConfigText(
            label="Homey address",
            placeholder="https://<homey-id>.connect.athom.com",
        ),
    )
    api_key: str = Parameter(
        default="",
        description="A personal API key created on Homey Pro 2023 or newer.",
        display=ConfigPassword(
            label="API key (Homey Pro 2023+)",
            placeholder="Paste your Homey API key",
        ),
    )
    verify_tls: bool = Parameter(
        default=True,
        display=ConfigToggle(label="Verify TLS certificates"),
    )
    timeout_seconds: int = Parameter(
        default=15,
        display=ConfigNumber(label="Request timeout (seconds)"),
    )

    def is_ready(self) -> bool:
        if not self.address.strip() or not self.api_key.strip():
            return False
        if self.timeout_seconds <= 0:
            return False
        try:
            normalize_base_url(self.address)
        except ValueError:
            return False
        return True


class HomeyIntegration(BaseIntegration[HomeyCredentials]):
    display_name = "Homey"
    image = HOMEY_IMAGE_URL
    providers = [
        IntegrationProviderDefinition(
            key="homey_oauth",
            auth_type="oauth2",
            display_name="Homey Account",
            image=HOMEY_IMAGE_URL,
            oauth2=OAuth2ProviderDefinition(
                authorize_url="https://api.athom.com/oauth2/authorise",
                token_url="https://api.athom.com/oauth2/token",  # nosec B106
                include_redirect_uri_in_token_request=False,
                token_response=OAuth2TokenResponseDefinition(
                    refresh_token_rotated=True
                ),
            ),
        )
    ]

    @classmethod
    async def is_ready(cls, creds: dict[str, Any] | None) -> bool:
        if creds is None:
            return False
        try:
            await _client_from_credentials(cls, creds).check_connection()
        except Exception:
            return False
        return True


def _client_from_credentials(
    integration: type[HomeyIntegration], creds: dict[str, Any]
) -> HomeyClient:
    access_token = creds.get("access_token")
    if isinstance(access_token, str) and access_token.strip():
        return HomeyClient(athom_access_token=access_token)

    parsed = integration.get_credentials(creds)
    if parsed is None or not parsed.is_ready():
        raise IntegrationFailedError(
            "Homey credentials are incomplete or invalid. Reconnect the Homey "
            "integration in Workspace control."
        )
    return HomeyClient(
        base_url=parsed.address,
        token=parsed.api_key,
        verify_tls=parsed.verify_tls,
        timeout_seconds=parsed.timeout_seconds,
    )


def client_from_ctx(ctx: RemoteExecutionContext) -> HomeyClient:
    creds = ctx.get_integration_credentials("homey") or {}
    try:
        return _client_from_credentials(HomeyIntegration, creds)
    except (TypeError, ValueError) as exc:
        raise IntegrationFailedError(
            "Homey credentials are incomplete or invalid. Reconnect the Homey "
            "integration in Workspace control."
        ) from exc
