from noxus_sdk.integrations import NangoIntegration, NangoProviderOAuthCredentials


class LinearIntegration(NangoIntegration):
    """Linear integration for accessing Linear API and managing issues"""

    name = "linear"
    display_name = "Linear"
    description = "Integration with Linear for project management and issue tracking"
    image = "https://storage.googleapis.com/image-storage-spot-manual/logos/external-integrations/external-integrations/linear.png"
    scopes = [
        "issues:read"
    ]

    # Nango specific
    provider = "linear"

    def get_nango_credentials(self, config: dict) -> NangoProviderOAuthCredentials:
        """Get the Nango credentials for this integration"""
        
        return NangoProviderOAuthCredentials(
            type="OAUTH2",
            client_id=config["client_id"],
            client_secret=config["client_secret"],
        )
