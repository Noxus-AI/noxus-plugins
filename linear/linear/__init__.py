"""Linear integration plugin for Noxus"""

from typing import Type

from noxus_sdk.plugins import BasePlugin
from noxus_sdk.nodes import BaseNode
from noxus_sdk.integrations import BaseIntegration

from linear.config import LinearPluginConfiguration
from linear.integration import LinearIntegration
from linear.nodes import (
    LinearIssuesReaderNode,
)


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
    
    def integrations(self) -> list[Type[BaseIntegration]]:
        """Return the integrations provided by this plugin"""
        return [
            LinearIntegration,
        ]