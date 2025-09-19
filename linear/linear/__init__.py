"""Linear integration plugin for Noxus"""

from typing import Type

from noxus_sdk.schemas import ValidationResult
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.nodes import BaseNode
from noxus_sdk.integrations import BaseIntegration
from noxus_sdk.ncl import APIKeyField, Parameter, ConfigText

from linear.integration import LinearIntegration
from linear.nodes import (
    LinearIssuesReaderNode,
)


class LinearPluginConfiguration(PluginConfiguration):
    """Linear plugin configuration"""

    client_id: str = Parameter(
        description="The Client ID of your Linear app",
        display=ConfigText(label="Linear Client ID", placeholder="Enter your Linear Client ID"),
    )
    client_secret: str = Parameter(
        description="The Client Secret of your Linear app",
        display=APIKeyField(label="Linear Client Secret", name="LINEAR_CLIENT_SECRET", key="LINEAR_CLIENT_SECRET"),
    )
    webhook_secret: str = Parameter(
        description="The Webhook Secret of your Linear app",
        display=APIKeyField(label="Linear Webhook Secret", name="LINEAR_WEBHOOK_SECRET", key="LINEAR_WEBHOOK_SECRET"),
    )

    def validate_config(self) -> ValidationResult:
        missing_fields = []
        if not self.client_id:
            missing_fields.append("Client ID")
        if not self.client_secret:
            missing_fields.append("Client Secret")
        if not self.webhook_secret:
            missing_fields.append("Webhook Secret")
        if missing_fields:
            error_message = "The following fields are required: " + ", ".join(missing_fields)
            return ValidationResult(valid=False, errors=[error_message])
        return ValidationResult(valid=True)


class LinearPlugin(BasePlugin[LinearPluginConfiguration]):
    """Linear integration plugin for Noxus"""

    # Plugin metadata (auto-detected from package if not set)
    name = "linear"
    display_name = "Linear"
    version = "0.1.0" 
    description = "Linear integration for reading issues from your workspace."
    author = "Noxus Team"
    image = "https://storage.googleapis.com/image-storage-spot-manual/logos/external-integrations/external-integrations/linear.png"
    
    def nodes(self) -> list[Type[BaseNode]]:
        """Return the nodes provided by this plugin"""
        return [
            LinearIssuesReaderNode,
        ]
    
    def integrations(self) -> list[Type[BaseIntegration]]:
        """Return the integrations provided by this plugin"""
        return [
            LinearIntegration,
        ]