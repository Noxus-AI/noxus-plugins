"""Minimal async client for the authenticated Homey HTTP API."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from noxus_sdk.errors import IntegrationFailedError

_ATHOM_API_URL = "https://api.athom.com"
_MAX_REQUEST_ATTEMPTS = 4
_INITIAL_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 30.0


def _retry_delay(response: httpx.Response, retry_number: int) -> float:
    """Return bounded exponential delay, respecting Retry-After when longer."""
    exponential = min(
        _INITIAL_BACKOFF_SECONDS * (2**retry_number),
        _MAX_BACKOFF_SECONDS,
    )
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return exponential

    try:
        requested = float(retry_after)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(retry_after)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            requested = (retry_at - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return exponential

    return min(max(exponential, requested, 0.0), _MAX_BACKOFF_SECONDS)


async def _request_with_backoff(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Retry rate-limited Homey requests with bounded exponential backoff."""
    for attempt in range(_MAX_REQUEST_ATTEMPTS):
        response = await client.request(method, url, **kwargs)
        if response.status_code != 429 or attempt == _MAX_REQUEST_ATTEMPTS - 1:
            return response
        await asyncio.sleep(_retry_delay(response, attempt))

    raise AssertionError("unreachable")


def normalize_base_url(value: str) -> str:
    """Validate and normalize a Homey address without changing its host."""
    raw = value.strip().rstrip("/")
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise ValueError("Homey address is not a valid URL") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Homey address must be an absolute http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ValueError("Homey address must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Homey address must not contain a query or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("Homey address must not contain an API path")

    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def parse_capability_value(raw: str) -> str | int | float | bool:
    """Parse a JSON scalar, falling back to plain text for enum values."""
    import json

    value = raw.strip()
    try:
        parsed: Any = json.loads(value)
    except json.JSONDecodeError:
        return raw

    if isinstance(parsed, bool | str):
        return parsed
    if isinstance(parsed, int):
        return parsed
    if isinstance(parsed, float) and math.isfinite(parsed):
        return parsed
    raise IntegrationFailedError(
        "Homey capability value must be a string, finite number, or boolean."
    )


class HomeyClient:
    """Call fixed Homey manager endpoints with bearer authentication."""

    def __init__(
        self,
        *,
        base_url: str = "",
        token: str = "",
        athom_access_token: str = "",
        homey_id: str = "",
        legacy_api: bool = False,
        verify_tls: bool = True,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.athom_access_token = athom_access_token.strip()
        self.base_url = normalize_base_url(base_url) if base_url.strip() else ""
        self.token = token.strip()
        self.homey_id = homey_id.strip()
        self.legacy_api = legacy_api
        if self.athom_access_token:
            if self.base_url or self.token:
                raise ValueError(
                    "Use either an Athom OAuth access token or direct Homey credentials"
                )
            # OAuth discovery selects a real Homey ID and remote URL lazily.
            self.legacy_api = True
        elif not self.base_url or not self.token:
            raise ValueError("A Homey address and API key are required")
        else:
            self.homey_id = self.homey_id or "token-homey"
        if timeout_seconds <= 0:
            raise ValueError("Homey timeout must be greater than zero")

        self.verify_tls = verify_tls
        self.timeout = httpx.Timeout(timeout_seconds)
        self.transport = transport

    async def check_connection(self) -> dict[str, Any]:
        result = await self._request("GET", "/api/manager/system/")
        if not isinstance(result, dict):
            raise IntegrationFailedError(
                "Homey returned an unexpected response to the authentication check."
            )
        return result

    async def list_devices(self) -> list[dict[str, Any]]:
        # Homey API v2 (used by the 2016–2019 models) specifies the collection
        # route with a trailing slash; API v3 specifies it without one.
        path = (
            "/api/manager/devices/device/"
            if self.legacy_api
            else "/api/manager/devices/device"
        )
        result = await self._request("GET", path)
        if isinstance(result, dict):
            devices = []
            for device_id, raw_device in result.items():
                if not isinstance(raw_device, dict):
                    continue
                device = dict(raw_device)
                device.setdefault("id", str(device_id))
                devices.append(device)
        elif isinstance(result, list):
            devices = [dict(device) for device in result if isinstance(device, dict)]
        else:
            raise IntegrationFailedError(
                "Homey returned an unexpected device-list response."
            )

        return sorted(
            devices,
            key=lambda device: (
                str(device.get("name", "")).casefold(),
                str(device.get("id", "")),
            ),
        )

    async def get_device(self, device_id: str) -> dict[str, Any]:
        result = await self._request(
            "GET", f"/api/manager/devices/device/{self._path_part(device_id)}"
        )
        if not isinstance(result, dict):
            raise IntegrationFailedError(
                "Homey returned an unexpected device response."
            )
        result.setdefault("id", device_id)
        return result

    async def list_flows(self, *, advanced: bool = False) -> list[dict[str, Any]]:
        flow_kind = "advancedflow" if advanced else "flow"
        path = f"/api/manager/flow/{flow_kind}"
        if self.legacy_api:
            path += "/"
        result = await self._request("GET", path)
        if isinstance(result, dict):
            flows = []
            for flow_id, raw_flow in result.items():
                if not isinstance(raw_flow, dict):
                    continue
                flow = dict(raw_flow)
                flow.setdefault("id", str(flow_id))
                flows.append(flow)
        elif isinstance(result, list):
            flows = [dict(flow) for flow in result if isinstance(flow, dict)]
        else:
            raise IntegrationFailedError(
                "Homey returned an unexpected flow-list response."
            )
        return sorted(
            flows,
            key=lambda flow: (
                str(flow.get("name", "")).casefold(),
                str(flow.get("id", "")),
            ),
        )

    async def set_capability_value(
        self,
        *,
        device_id: str,
        capability_id: str,
        value: str | int | float | bool,
    ) -> None:
        await self._request(
            "PUT",
            "/api/manager/devices/device/"
            f"{self._path_part(device_id)}/capability/"
            f"{self._path_part(capability_id)}",
            json_body={"value": value},
        )

    async def trigger_flow(self, *, flow_id: str, advanced: bool) -> None:
        flow_kind = "advancedflow" if advanced else "flow"
        await self._request(
            "POST",
            f"/api/manager/flow/{flow_kind}/{self._path_part(flow_id)}/trigger",
            json_body={},
        )

    @staticmethod
    def _path_part(value: str) -> str:
        clean = value.strip()
        if not clean:
            raise IntegrationFailedError("Homey identifier cannot be empty.")
        return quote(clean, safe="")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        await self._ensure_homey_session()
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            # Homey's official client sends this header. A real Homey ID is
            # accepted for OAuth-derived sessions; direct API-key mode uses
            # the same fallback identifier as the official Homey CLI.
            "X-Homey-ID": self.homey_id,
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_tls,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await _request_with_backoff(
                    client,
                    method,
                    path,
                    json=json_body,
                )
        except httpx.TimeoutException as exc:
            raise IntegrationFailedError(
                f"Timed out while connecting to Homey at {self.base_url}."
            ) from exc
        except httpx.HTTPError as exc:
            raise IntegrationFailedError(
                f"Could not connect to Homey at {self.base_url}: {exc}"
            ) from exc

        if response.is_error:
            raise self._response_error(response)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise IntegrationFailedError(
                "Homey returned a non-JSON API response."
            ) from exc

    def _response_error(self, response: httpx.Response) -> IntegrationFailedError:
        detail = ""
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            raw_detail = (
                body.get("error_description")
                or body.get("message")
                or body.get("error")
            )
            if raw_detail:
                detail = f": {str(raw_detail)[:500]}"
        detail = detail.replace(self.token, "<redacted>")

        if response.status_code == 401:
            message = "Homey rejected the API key or bearer token"
        elif response.status_code == 403:
            message = "Homey credential does not have permission for this action"
        elif response.status_code == 404:
            message = "Homey could not find the requested device, capability, or flow"
        elif response.status_code == 429:
            message = (
                f"Homey rate limit remained active after "
                f"{_MAX_REQUEST_ATTEMPTS} attempts"
            )
        else:
            message = f"Homey API request failed with status {response.status_code}"
        return IntegrationFailedError(f"{message}{detail}")

    async def _ensure_homey_session(self) -> None:
        """Discover Homey's cloud URL and exchange OAuth for a Homey session."""
        if not self.athom_access_token or self.token:
            return

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.athom_access_token}",
        }
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_tls,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                user_response = await _request_with_backoff(
                    client,
                    "GET",
                    f"{_ATHOM_API_URL}/user/me",
                )
                user = self._oauth_response_json(user_response, "load Homeys")
                if not isinstance(user, dict) or not isinstance(
                    user.get("homeys"), list
                ):
                    raise IntegrationFailedError(
                        "Athom returned an unexpected Homey account response."
                    )

                homeys = [item for item in user["homeys"] if isinstance(item, dict)]
                selected = None
                if self.homey_id:
                    selected = next(
                        (
                            item
                            for item in homeys
                            if str(item.get("_id", "")) == self.homey_id
                        ),
                        None,
                    )
                else:
                    selected = next(
                        (item for item in homeys if item.get("remoteUrl")), None
                    )

                if selected is None:
                    raise IntegrationFailedError(
                        "No remotely reachable Homey was found on this Athom account."
                    )

                homey_id = str(selected.get("_id", "")).strip()
                remote_url = str(selected.get("remoteUrl", "")).strip()
                if not homey_id or not remote_url:
                    raise IntegrationFailedError(
                        "The selected Homey has no Homey ID or remote API URL."
                    )

                delegation_response = await _request_with_backoff(
                    client,
                    "POST",
                    f"{_ATHOM_API_URL}/delegation/token?audience=homey",
                )
                delegation_token = self._oauth_response_json(
                    delegation_response, "create a Homey delegation token"
                )
                if not isinstance(delegation_token, str) or not delegation_token:
                    raise IntegrationFailedError(
                        "Athom returned an unexpected delegation-token response."
                    )

            # The Homey session endpoint receives the delegation token, not
            # the Athom access token. Use a separate client so the Athom bearer
            # header is never forwarded, and use remoteUrl deliberately so a
            # Noxus sandbox never needs access to the user's private LAN.
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_tls,
                follow_redirects=False,
                transport=self.transport,
            ) as homey_client:
                session_response = await _request_with_backoff(
                    homey_client,
                    "POST",
                    f"{normalize_base_url(remote_url)}/api/manager/users/login",
                    headers={"Content-Type": "application/json"},
                    json={"token": delegation_token},
                )
                session_token = self._oauth_response_json(
                    session_response, "create a Homey session"
                )
        except IntegrationFailedError:
            raise
        except httpx.TimeoutException as exc:
            raise IntegrationFailedError(
                "Timed out while connecting to the Homey cloud API."
            ) from exc
        except httpx.HTTPError as exc:
            raise IntegrationFailedError(
                f"Could not connect to the Homey cloud API: {exc}"
            ) from exc

        if not isinstance(session_token, str) or not session_token.strip():
            raise IntegrationFailedError(
                "Homey returned an unexpected session-token response."
            )

        self.base_url = normalize_base_url(remote_url)
        self.homey_id = homey_id
        self.token = session_token.strip()

    def _oauth_response_json(self, response: httpx.Response, action: str) -> Any:
        if response.is_error:
            detail = ""
            try:
                body = response.json()
            except ValueError:
                body = None
            if isinstance(body, dict):
                raw_detail = (
                    body.get("error_description")
                    or body.get("message")
                    or body.get("error")
                )
                if raw_detail:
                    detail = f": {str(raw_detail)[:500]}"
            detail = detail.replace(self.athom_access_token, "<redacted>")
            if response.status_code == 429:
                raise IntegrationFailedError(
                    f"Could not {action}: Homey rate limit remained active after "
                    f"{_MAX_REQUEST_ATTEMPTS} attempts{detail}"
                )
            raise IntegrationFailedError(
                f"Could not {action}: Homey returned status "
                f"{response.status_code}{detail}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise IntegrationFailedError(
                f"Could not {action}: Homey returned a non-JSON response."
            ) from exc
