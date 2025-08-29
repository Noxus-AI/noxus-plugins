"""Linear integration plugin for Noxus"""

from typing import Type

from noxus_sdk.schemas import ValidationResult
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.nodes import BaseNode
from noxus_sdk.ncl import APIKeyField, Parameter, ConfigText

from linear.nodes import (
    LinearIssuesReaderNode,
)


class LinearPluginConfiguration(PluginConfiguration):
    """Linear plugin configuration"""

    api_key: str = Parameter(
        description="The API key for your Linear workspace",
        display=APIKeyField(
            label="Linear API Key",
            name="LINEAR_API_KEY",
            key="LINEAR_API_KEY",
        ),
    )
    other_param: str = Parameter(
        description="Other parameter",
        display=ConfigText(label="Other parameter"),
    )

    def validate_config(self) -> ValidationResult:
        if self.other_param != "test":
            return ValidationResult(valid=False, errors=["Other parameter must be 'test'"])
        return ValidationResult(valid=True)


class LinearPlugin(BasePlugin[LinearPluginConfiguration]):
    """Linear integration plugin for Noxus"""

    # Plugin metadata (auto-detected from package if not set)
    name = "linear"
    display_name = "Linear"
    version = "0.1.0"
    description = "Linear integration for reading issues from your workspace"
    tags = ["linear", "project-management", "integration", "issues"]
    author = "Noxus Team"
    image = "https://storage.googleapis.com/image-storage-spot-manual/logos/external-integrations/external-integrations/linear.png"

    # Execution configuration
    execution = "runtime"

    def nodes(self) -> list[Type[BaseNode]]:
        """Return the nodes provided by this plugin"""
        return [
            LinearIssuesReaderNode,
        ]
