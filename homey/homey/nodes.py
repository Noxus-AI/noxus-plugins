"""Authenticated Homey control nodes."""

from __future__ import annotations

import json
from typing import Any

from noxus_sdk.errors import IntegrationFailedError
from noxus_sdk.ncl import ConfigBigText, ConfigSelect, Parameter
from noxus_sdk.nodes.base import BaseNodeV2, NodeConfiguration, NodeOutputs
from noxus_sdk.nodes.schemas import ConfigResponse
from noxus_sdk.nodes.types import NodeCategory
from noxus_sdk.plugins.context import RemoteExecutionContext

from homey.client import parse_capability_value
from homey.integration import HOMEY_IMAGE_URL, client_from_ctx

_IMAGE = HOMEY_IMAGE_URL
_DOCUMENTATION_URL = "https://api.developer.homey.app/"


def _options(
    items: list[dict[str, Any]], *, fallback_label: str
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for item in items:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        label = str(item.get("name") or item.get("title") or fallback_label).strip()
        options.append({"value": item_id, "label": label or item_id})
    return options


def _capability_options(device: dict[str, Any]) -> list[dict[str, str]]:
    capabilities_obj = device.get("capabilitiesObj")
    if isinstance(capabilities_obj, dict):
        options: list[dict[str, str]] = []
        for capability_id, capability in capabilities_obj.items():
            label = (
                capability.get("title")
                if isinstance(capability, dict)
                else capability_id
            )
            options.append(
                {
                    "value": str(capability_id),
                    "label": str(label or capability_id),
                }
            )
        return options
    capabilities = device.get("capabilities")
    if isinstance(capabilities, list):
        return [
            {"value": str(capability), "label": str(capability)}
            for capability in capabilities
        ]
    return []


class ListHomeyDevicesConfig(NodeConfiguration):
    pass


class ListHomeyDevicesOutputs(NodeOutputs):
    devices: list[dict]
    count: int


class ListHomeyDevicesNode(BaseNodeV2[ListHomeyDevicesConfig, ListHomeyDevicesOutputs]):
    node_name = "ListHomeyDevicesNode"
    title = "List Homey devices"
    description = "Lists devices and their current capabilities from Homey."
    small_description = "List devices from Homey"
    category = NodeCategory.INTEGRATIONS
    sub_category = "Homey"
    color = "#080B14"
    image = _IMAGE
    documentation_url = _DOCUMENTATION_URL
    integrations = {"homey": []}

    async def call(self, ctx: RemoteExecutionContext) -> dict[str, Any]:
        devices = await client_from_ctx(ctx).list_devices()
        return {"devices": devices, "count": len(devices)}


class GetHomeyDeviceConfig(NodeConfiguration):
    device_id: str = Parameter(
        description="The Homey device ID.",
        display=ConfigSelect(
            label="Device",
            values=[],
            placeholder="Select a Homey device",
        ),
    )


class GetHomeyDeviceOutputs(NodeOutputs):
    device: dict


class GetHomeyDeviceNode(BaseNodeV2[GetHomeyDeviceConfig, GetHomeyDeviceOutputs]):
    node_name = "GetHomeyDeviceNode"
    title = "Get Homey device"
    description = "Gets one Homey device and its current capability values."
    small_description = "Read a Homey device"
    category = NodeCategory.INTEGRATIONS
    sub_category = "Homey"
    color = "#080B14"
    image = _IMAGE
    documentation_url = _DOCUMENTATION_URL
    integrations = {"homey": []}

    @classmethod
    async def get_config(
        cls,
        ctx: RemoteExecutionContext,
        config_response: ConfigResponse,
        *,
        skip_cache: bool = False,
    ) -> ConfigResponse:
        del skip_cache
        config_response.config_values["device_id"] = _options(
            await client_from_ctx(ctx).list_devices(), fallback_label="Homey device"
        )
        return config_response

    async def call(self, ctx: RemoteExecutionContext) -> dict[str, Any]:
        device = await client_from_ctx(ctx).get_device(self.config.device_id)
        return {"device": device}


class SetHomeyCapabilityConfig(NodeConfiguration):
    device_id: str = Parameter(
        description="The Homey device ID.",
        display=ConfigSelect(
            label="Device",
            values=[],
            placeholder="Select a Homey device",
        ),
    )
    capability_id: str = Parameter(
        description="A capability such as onoff, dim, or target_temperature.",
        display=ConfigSelect(
            label="Capability",
            values=[],
            placeholder="Select a capability",
        ),
    )
    value: str = Parameter(
        bindable=True,
        description=(
            "A JSON string, number, or boolean. Unquoted text is treated as a string."
        ),
        display=ConfigBigText(
            label="Value",
            placeholder='true, 0.5, 21.5, or "heat"',
            number_of_lines=2,
        ),
    )


class SetHomeyCapabilityOutputs(NodeOutputs):
    device_id: str
    capability_id: str
    value: str


class SetHomeyCapabilityNode(
    BaseNodeV2[SetHomeyCapabilityConfig, SetHomeyCapabilityOutputs]
):
    node_name = "SetHomeyCapabilityNode"
    title = "Set Homey capability"
    description = "Changes a capability value on a Homey device."
    small_description = "Control a Homey device"
    category = NodeCategory.INTEGRATIONS
    sub_category = "Homey"
    color = "#080B14"
    image = _IMAGE
    documentation_url = _DOCUMENTATION_URL
    integrations = {"homey": []}

    @classmethod
    async def get_config(
        cls,
        ctx: RemoteExecutionContext,
        config_response: ConfigResponse,
        *,
        skip_cache: bool = False,
    ) -> ConfigResponse:
        del skip_cache
        selected_device = config_response.config_values.get("device_id")
        client = client_from_ctx(ctx)
        devices = await client.list_devices()
        resolved: dict[str, Any] = {
            "device_id": _options(devices, fallback_label="Homey device"),
            "capability_id": [],
        }
        if isinstance(selected_device, str) and selected_device:
            device = next(
                (d for d in devices if str(d.get("id", "")) == selected_device),
                None,
            )
            if device is None:
                device = await client.get_device(selected_device)
            resolved["capability_id"] = _capability_options(device)
        config_response.config_values = resolved
        return config_response

    async def call(self, ctx: RemoteExecutionContext) -> dict[str, Any]:
        value = parse_capability_value(self.config.value)
        await client_from_ctx(ctx).set_capability_value(
            device_id=self.config.device_id,
            capability_id=self.config.capability_id,
            value=value,
        )
        return {
            "device_id": self.config.device_id,
            "capability_id": self.config.capability_id,
            "value": json.dumps(value, ensure_ascii=False),
        }


class TriggerHomeyFlowConfig(NodeConfiguration):
    flow_type: str = Parameter(
        default="standard",
        display=ConfigSelect(
            label="Flow type",
            values=["standard", "advanced"],
        ),
    )
    flow_id: str = Parameter(
        description="The standard or Advanced Flow ID.",
        display=ConfigSelect(
            label="Flow",
            values=[],
            placeholder="Select a Homey Flow",
        ),
    )


class TriggerHomeyFlowOutputs(NodeOutputs):
    flow_id: str
    flow_type: str
    triggered: bool


class TriggerHomeyFlowNode(BaseNodeV2[TriggerHomeyFlowConfig, TriggerHomeyFlowOutputs]):
    node_name = "TriggerHomeyFlowNode"
    title = "Trigger Homey Flow"
    description = "Starts a standard or Advanced Flow on Homey."
    small_description = "Start a Homey Flow"
    category = NodeCategory.INTEGRATIONS
    sub_category = "Homey"
    color = "#080B14"
    image = _IMAGE
    documentation_url = _DOCUMENTATION_URL
    integrations = {"homey": []}

    @classmethod
    async def get_config(
        cls,
        ctx: RemoteExecutionContext,
        config_response: ConfigResponse,
        *,
        skip_cache: bool = False,
    ) -> ConfigResponse:
        del skip_cache
        flow_type = config_response.config_values.get("flow_type", "standard")
        config_response.config_values["flow_id"] = _options(
            await client_from_ctx(ctx).list_flows(advanced=flow_type == "advanced"),
            fallback_label="Homey Flow",
        )
        return config_response

    async def call(self, ctx: RemoteExecutionContext) -> dict[str, Any]:
        if self.config.flow_type not in {"standard", "advanced"}:
            raise IntegrationFailedError(
                "Homey Flow type must be 'standard' or 'advanced'."
            )
        await client_from_ctx(ctx).trigger_flow(
            flow_id=self.config.flow_id,
            advanced=self.config.flow_type == "advanced",
        )
        return {
            "flow_id": self.config.flow_id,
            "flow_type": self.config.flow_type,
            "triggered": True,
        }


HOMEY_NODES = [
    ListHomeyDevicesNode,
    GetHomeyDeviceNode,
    SetHomeyCapabilityNode,
    TriggerHomeyFlowNode,
]
