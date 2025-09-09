
from noxus_sdk.integrations import NangoIntegration, NangoProviderOAuthCredentials
from noxus_sdk.plugins.context import RemoteExecutionContext



class LinearIntegration(NangoIntegration):
    """Linear integration for accessing Linear API and managing issues"""

    name = "linear"
    display_name = "Linear"
    description = "Integration with Linear for project management and issue tracking."
    image = "https://storage.googleapis.com/image-storage-spot-manual/logos/external-integrations/external-integrations/linear.png"
    scopes = [
        "issues:read"
    ]

    # Nango specific
    provider = "linear"
    window_height = 600
    window_width = 600

    @classmethod
    def get_provider_credentials(cls, ctx: RemoteExecutionContext) -> NangoProviderOAuthCredentials:
        """Get the Nango credentials for this integration"""
        return NangoProviderOAuthCredentials(
            type="OAUTH2",
            client_id=ctx.plugin_config["client_id"],
            client_secret=ctx.plugin_config["client_secret"],
            webhook_secret=ctx.plugin_config["webhook_secret"],
        )
