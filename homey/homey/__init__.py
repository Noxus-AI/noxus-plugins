"""Authenticated Athom Homey control plugin for Noxus."""

from __future__ import annotations

from noxus_sdk.integrations.base import BaseIntegration
from noxus_sdk.nodes.base import BaseNode
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.types import PluginCategory

from homey.integration import HOMEY_IMAGE_URL, HomeyIntegration
from homey.nodes import HOMEY_NODES


class HomeyPluginConfig(PluginConfiguration):
    pass


class HomeyPlugin(BasePlugin[HomeyPluginConfig]):
    name = "homey"
    display_name = "Homey"
    version = "0.1.0"
    description = (
        "Control Athom Homey devices and flows with managed OAuth or API-key "
        "authentication."
    )
    category = PluginCategory.OTHER
    author = "Noxus Team"
    image = HOMEY_IMAGE_URL

    def integrations(self) -> list[type[BaseIntegration]]:
        return [HomeyIntegration]

    def nodes(self) -> list[type[BaseNode]]:
        return HOMEY_NODES


__all__ = ["HomeyPlugin"]
