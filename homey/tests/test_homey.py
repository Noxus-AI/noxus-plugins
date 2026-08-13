from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from noxus_sdk.errors import IntegrationFailedError
from noxus_sdk.nodes.schemas import ConfigResponse

from homey import HomeyPlugin
from homey.client import HomeyClient, normalize_base_url, parse_capability_value
from homey.integration import (
    HOMEY_IMAGE_URL,
    HomeyCredentials,
    HomeyIntegration,
    client_from_ctx,
)
from homey.nodes import (
    GetHomeyDeviceConfig,
    GetHomeyDeviceNode,
    ListHomeyDevicesNode,
    SetHomeyCapabilityConfig,
    SetHomeyCapabilityNode,
    TriggerHomeyFlowConfig,
    TriggerHomeyFlowNode,
)


def test_plugin_manifest_contains_integration_and_v2_nodes() -> None:
    manifest = HomeyPlugin.get_manifest()

    assert manifest.image == HOMEY_IMAGE_URL
    assert [integration.type for integration in manifest.integrations] == ["homey"]
    assert manifest.integrations[0].image == HOMEY_IMAGE_URL
    assert [provider.key for provider in manifest.integrations[0].providers] == [
        "homey_oauth"
    ]
    oauth = manifest.integrations[0].providers[0].oauth2
    assert oauth is not None
    assert oauth.authorization_code_param == "code"
    assert oauth.response_type_param == "response_type"
    assert oauth.extra_authorize_params == {}
    assert oauth.include_redirect_uri_in_token_request is False
    assert manifest.nodes == []
    assert [node.type for node in manifest.nodes_v2] == [
        "ListHomeyDevicesNode",
        "GetHomeyDeviceNode",
        "SetHomeyCapabilityNode",
        "TriggerHomeyFlowNode",
    ]
    assert [node.node_name for node in HomeyPlugin().nodes()] == [
        ListHomeyDevicesNode.node_name,
        GetHomeyDeviceNode.node_name,
        SetHomeyCapabilityNode.node_name,
        TriggerHomeyFlowNode.node_name,
    ]
    assert {node.image for node in manifest.nodes_v2} == {HOMEY_IMAGE_URL}


def test_api_key_secret_is_masked_and_bearer_token_is_not_user_config() -> None:
    definition = HomeyIntegration.get_definition()

    assert definition.config["api_key"]["display"]["type"] == "password"
    assert definition.config["address"]["display"]["type"] == "text"
    assert "bearer_token" not in definition.config
    assert "client_secret" not in definition.config


def test_api_key_credentials_require_address_and_key() -> None:
    common = {"address": "http://homey.local"}

    assert HomeyCredentials(**common, api_key="new-key").is_ready()
    assert not HomeyCredentials(**common).is_ready()
    assert not HomeyCredentials(api_key="new-key").is_ready()


def test_client_from_context_selects_managed_oauth_token() -> None:
    class Context:
        def get_integration_credentials(self, name: str) -> dict[str, Any]:
            assert name == "homey"
            return {
                "access_token": "athom-access-token",
                "refresh_token": "managed-by-noxus",
            }

    client = client_from_ctx(Context())  # type: ignore[arg-type]

    assert client.athom_access_token == "athom-access-token"
    assert client.token == ""
    assert client.base_url == ""
    assert client.legacy_api is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("false", False),
        ("0.5", 0.5),
        ("21", 21),
        ('"heat"', "heat"),
        ("heat", "heat"),
    ],
)
def test_parse_capability_value(raw: str, expected: object) -> None:
    assert parse_capability_value(raw) == expected


@pytest.mark.parametrize("raw", ["null", "[]", "{}", "NaN", "Infinity"])
def test_parse_capability_value_rejects_non_scalars(raw: str) -> None:
    with pytest.raises(IntegrationFailedError):
        parse_capability_value(raw)


def test_normalize_base_url_rejects_unsafe_shapes() -> None:
    assert normalize_base_url(" https://homey.local/ ") == "https://homey.local"

    for invalid in (
        "homey.local",
        "ftp://homey.local",
        "http://user:secret@homey.local",
        "http://homey.local/api/manager",
        "http://homey.local?token=secret",
    ):
        with pytest.raises(ValueError):
            normalize_base_url(invalid)


@pytest.mark.asyncio
async def test_list_devices_uses_bearer_auth_and_normalizes_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/manager/devices/device"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["X-Homey-ID"] == "token-homey"
        return httpx.Response(
            200,
            json={
                "device-b": {"name": "Zigbee plug"},
                "device-a": {"id": "device-a", "name": "Desk light"},
            },
        )

    client = HomeyClient(
        base_url="http://homey.local",
        token="test-key",
        transport=httpx.MockTransport(handler),
    )

    assert await client.list_devices() == [
        {"id": "device-a", "name": "Desk light"},
        {"id": "device-b", "name": "Zigbee plug"},
    ]


@pytest.mark.asyncio
async def test_requests_retry_429_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(429, json={"message": "Too many requests"})
        return httpx.Response(200, json={})

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("homey.client.asyncio.sleep", fake_sleep)
    client = HomeyClient(
        base_url="http://homey.local",
        token="test-key",
        transport=httpx.MockTransport(handler),
    )

    assert await client.list_devices() == []
    assert attempts == 3
    assert delays == [1.0, 2.0]


@pytest.mark.asyncio
async def test_requests_stop_after_four_rate_limit_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, json={"message": "Too many requests"})

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("homey.client.asyncio.sleep", fake_sleep)
    client = HomeyClient(
        base_url="http://homey.local",
        token="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(IntegrationFailedError, match="after 4 attempts"):
        await client.list_devices()
    assert attempts == 4
    assert delays == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_oauth_discovers_remote_url_and_creates_homey_session() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "api.athom.com" and request.url.path == "/user/me":
            assert request.headers["Authorization"] == "Bearer athom-access-token"
            return httpx.Response(
                200,
                json={
                    "homeys": [
                        {
                            "_id": "homey-2019",
                            "localUrl": "http://192.168.1.100",
                            "remoteUrl": "https://homey-2019.homeypro.net",
                        }
                    ]
                },
            )
        if (
            request.url.host == "api.athom.com"
            and request.url.path == "/delegation/token"
        ):
            assert request.url.params["audience"] == "homey"
            assert request.headers["Authorization"] == "Bearer athom-access-token"
            return httpx.Response(200, json="delegation-token")
        if request.url.path == "/api/manager/users/login":
            assert "Authorization" not in request.headers
            assert json.loads(request.content) == {"token": "delegation-token"}
            return httpx.Response(200, json="session-token")

        assert request.url.host == "homey-2019.homeypro.net"
        assert request.url.raw_path == b"/api/manager/devices/device/"
        assert request.headers["Authorization"] == "Bearer session-token"
        assert request.headers["X-Homey-ID"] == "homey-2019"
        return httpx.Response(200, json={})

    client = HomeyClient(
        athom_access_token="athom-access-token",
        transport=httpx.MockTransport(handler),
    )

    assert await client.list_devices() == []
    assert client.base_url == "https://homey-2019.homeypro.net"
    assert [request.url.path for request in requests] == [
        "/user/me",
        "/delegation/token",
        "/api/manager/users/login",
        "/api/manager/devices/device/",
    ]


@pytest.mark.asyncio
async def test_oauth_discovery_retries_429_and_honors_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_attempts = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal user_attempts
        if request.url.path == "/user/me":
            user_attempts += 1
            if user_attempts == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "5"},
                    json={"message": "Too many requests"},
                )
            return httpx.Response(
                200,
                json={
                    "homeys": [
                        {
                            "_id": "homey-2019",
                            "remoteUrl": "https://homey-2019.homeypro.net",
                        }
                    ]
                },
            )
        if request.url.path == "/delegation/token":
            return httpx.Response(200, json="delegation-token")
        if request.url.path == "/api/manager/users/login":
            return httpx.Response(200, json="session-token")
        return httpx.Response(200, json={})

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("homey.client.asyncio.sleep", fake_sleep)
    client = HomeyClient(
        athom_access_token="athom-access-token",
        transport=httpx.MockTransport(handler),
    )

    assert await client.list_devices() == []
    assert user_attempts == 2
    assert delays == [5.0]


@pytest.mark.asyncio
async def test_set_capability_and_trigger_advanced_flow() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    client = HomeyClient(
        base_url="http://homey.local",
        token="test-key",
        homey_id="homey-2019",
        transport=httpx.MockTransport(handler),
    )
    await client.set_capability_value(
        device_id="device/with slash",
        capability_id="onoff",
        value=True,
    )
    await client.trigger_flow(flow_id="flow/one", advanced=True)

    assert requests[0].method == "PUT"
    assert requests[0].headers["X-Homey-ID"] == "homey-2019"
    assert requests[0].url.raw_path == (
        b"/api/manager/devices/device/device%2Fwith%20slash/capability/onoff"
    )
    assert json.loads(requests[0].content) == {"value": True}
    assert requests[1].method == "POST"
    assert requests[1].url.raw_path == (
        b"/api/manager/flow/advancedflow/flow%2Fone/trigger"
    )


@pytest.mark.asyncio
async def test_list_flows_normalizes_and_sorts_legacy_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/api/manager/flow/advancedflow/"
        return httpx.Response(
            200,
            json={
                "flow-b": {"name": "Wake up"},
                "flow-a": {"name": "Arrive home"},
            },
        )

    client = HomeyClient(
        athom_access_token="athom-token",
        transport=httpx.MockTransport(handler),
    )
    client.base_url = "https://homey.test"
    client.homey_id = "homey-2019"
    client.token = "session-token"

    assert await client.list_flows(advanced=True) == [
        {"name": "Arrive home", "id": "flow-a"},
        {"name": "Wake up", "id": "flow-b"},
    ]


@pytest.mark.asyncio
async def test_homey_node_configs_resolve_devices_capabilities_and_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        async def list_devices(self) -> list[dict[str, Any]]:
            return [
                {
                    "id": "lamp-1",
                    "name": "Desk lamp",
                    "capabilitiesObj": {
                        "onoff": {"title": "On or off"},
                        "dim": {"title": "Brightness"},
                    },
                }
            ]

        async def get_device(self, device_id: str) -> dict[str, Any]:
            raise AssertionError(f"unexpected device lookup: {device_id}")

        async def list_flows(self, *, advanced: bool) -> list[dict[str, Any]]:
            assert advanced is True
            return [{"id": "flow-1", "name": "Welcome home"}]

    monkeypatch.setattr("homey.nodes.client_from_ctx", lambda ctx: FakeClient())

    device_response = await GetHomeyDeviceNode.get_config(
        object(),  # type: ignore[arg-type]
        ConfigResponse(config={}, inputs=[], outputs=[]),
    )
    assert device_response.config_values["device_id"] == [
        {"value": "lamp-1", "label": "Desk lamp"}
    ]

    capability_response = await SetHomeyCapabilityNode.get_config(
        object(),  # type: ignore[arg-type]
        ConfigResponse(
            config={},
            inputs=[],
            outputs=[],
            config_values={"device_id": "lamp-1"},
        ),
    )
    assert capability_response.config_values["capability_id"] == [
        {"value": "onoff", "label": "On or off"},
        {"value": "dim", "label": "Brightness"},
    ]

    flow_response = await TriggerHomeyFlowNode.get_config(
        object(),  # type: ignore[arg-type]
        ConfigResponse(
            config={},
            inputs=[],
            outputs=[],
            config_values={"flow_type": "advanced"},
        ),
    )
    assert flow_response.config_values["flow_id"] == [
        {"value": "flow-1", "label": "Welcome home"}
    ]

    assert (
        GetHomeyDeviceConfig.model_fields["device_id"].json_schema_extra.get("bindable")
        is not True
    )
    assert (
        SetHomeyCapabilityConfig.model_fields["capability_id"].json_schema_extra.get(
            "bindable"
        )
        is not True
    )
    assert (
        TriggerHomeyFlowConfig.model_fields["flow_id"].json_schema_extra.get("bindable")
        is not True
    )


@pytest.mark.asyncio
async def test_homey_api_errors_are_actionable_and_redact_the_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error_description": "bad key test-key"},
        )

    client = HomeyClient(
        base_url="http://homey.local",
        token="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(IntegrationFailedError) as exc_info:
        await client.list_devices()
    assert "rejected the API key or bearer token" in str(exc_info.value)
    assert "test-key" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_set_capability_node_parses_and_reports_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeClient:
        async def set_capability_value(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    monkeypatch.setattr("homey.nodes.client_from_ctx", lambda ctx: FakeClient())
    node = SetHomeyCapabilityNode(
        SetHomeyCapabilityConfig(
            device_id="device-a",
            capability_id="onoff",
            value="true",
        )
    )

    result = await node.call(object())  # type: ignore[arg-type]

    assert calls == [{"device_id": "device-a", "capability_id": "onoff", "value": True}]
    assert result == {
        "device_id": "device-a",
        "capability_id": "onoff",
        "value": "true",
    }
