from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []

    const_mod = types.ModuleType("homeassistant.const")
    const_mod.CONF_HOST = "host"
    const_mod.CONF_PORT = "port"

    core_mod = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    class ServiceCall:
        def __init__(self, data: dict[str, Any]) -> None:
            self.data = data

    core_mod.HomeAssistant = HomeAssistant
    core_mod.ServiceCall = ServiceCall

    exceptions_mod = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    class ServiceValidationError(HomeAssistantError):
        pass

    exceptions_mod.HomeAssistantError = HomeAssistantError
    exceptions_mod.ServiceValidationError = ServiceValidationError

    config_entries_mod = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        def __init__(self, *, data: dict[str, Any], entry_id: str = "entry-1") -> None:
            self.data = data
            self.entry_id = entry_id
            self.runtime_data = None

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs) -> None:
            return None

        def __init__(self) -> None:
            self.hass = None
            self._unique_id: str | None = None
            self._configured_ids: set[str] = set()

        async def async_set_unique_id(self, unique_id: str) -> None:
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            if self._unique_id in self._configured_ids:
                raise RuntimeError("already_configured")

        def async_show_form(self, *, step_id: str, data_schema: Any, errors: dict[str, str]):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors,
            }

        def async_create_entry(self, *, title: str, data: dict[str, Any]):
            return {"type": "create_entry", "title": title, "data": data}

    config_entries_mod.ConfigEntry = ConfigEntry
    config_entries_mod.ConfigFlow = ConfigFlow

    helpers_pkg = types.ModuleType("homeassistant.helpers")
    helpers_pkg.__path__ = []

    aiohttp_client_mod = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client_mod.async_get_clientsession = lambda hass: object()

    update_coordinator_mod = types.ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass: Any, logger: Any, name: str, update_interval: Any) -> None:
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None

        async def async_config_entry_first_refresh(self) -> None:
            self.data = await self._async_update_data()

        async def async_request_refresh(self) -> None:
            self.data = await self._async_update_data()

        def async_set_updated_data(self, data: Any) -> None:
            self.data = data

    class CoordinatorEntity:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, coordinator: DataUpdateCoordinator) -> None:
            self.coordinator = coordinator

    update_coordinator_mod.UpdateFailed = UpdateFailed
    update_coordinator_mod.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator_mod.CoordinatorEntity = CoordinatorEntity

    entity_mod = types.ModuleType("homeassistant.helpers.entity")

    @dataclass
    class DeviceInfo:
        identifiers: set[tuple[str, str]]
        name: str
        manufacturer: str
        model: str

    entity_mod.DeviceInfo = DeviceInfo

    entity_platform_mod = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform_mod.AddEntitiesCallback = Any

    components_pkg = types.ModuleType("homeassistant.components")
    components_pkg.__path__ = []

    components_sensor_mod = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:
        pass

    components_sensor_mod.SensorEntity = SensorEntity

    components_switch_mod = types.ModuleType("homeassistant.components.switch")

    class SwitchEntity:
        pass

    components_switch_mod.SwitchEntity = SwitchEntity

    components_tts_mod = types.ModuleType("homeassistant.components.tts")

    class TextToSpeechEntity:
        pass

    components_tts_mod.TextToSpeechEntity = TextToSpeechEntity

    vol_mod = types.ModuleType("voluptuous")

    def _identity(*args, **kwargs):
        if args:
            return args[0]
        return lambda value: value

    class _Length:
        def __init__(self, min: int | None = None, max: int | None = None) -> None:
            self.min = min
            self.max = max

        def __call__(self, value: Any) -> Any:
            return value

    class _Range:
        def __init__(self, min: int | None = None, max: int | None = None) -> None:
            self.min = min
            self.max = max

        def __call__(self, value: Any) -> Any:
            return value

    class _Schema:
        def __init__(self, schema: Any) -> None:
            self.schema = schema

        def __call__(self, value: Any) -> Any:
            return value

    vol_mod.Required = _identity
    vol_mod.Optional = _identity
    vol_mod.All = _identity
    vol_mod.Coerce = _identity
    vol_mod.Length = _Length
    vol_mod.Range = _Range
    vol_mod.Schema = _Schema

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.const"] = const_mod
    sys.modules["homeassistant.core"] = core_mod
    sys.modules["homeassistant.exceptions"] = exceptions_mod
    sys.modules["homeassistant.config_entries"] = config_entries_mod
    sys.modules["homeassistant.helpers"] = helpers_pkg
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client_mod
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator_mod
    sys.modules["homeassistant.helpers.entity"] = entity_mod
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform_mod
    sys.modules["homeassistant.components"] = components_pkg
    sys.modules["homeassistant.components.sensor"] = components_sensor_mod
    sys.modules["homeassistant.components.switch"] = components_switch_mod
    sys.modules["homeassistant.components.tts"] = components_tts_mod
    sys.modules["voluptuous"] = vol_mod


_install_homeassistant_stubs()


class _MockResponse:
    def __init__(
        self,
        status: int,
        payload: Any = None,
        text_body: str = "",
        content_type: str | None = None,
        body_bytes: bytes | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self._text_body = text_body
        self._body_bytes = body_bytes
        if content_type is not None:
            self.content_type = content_type
        else:
            self.content_type = "application/json" if payload is not None else "text/plain"
        self.headers = {"Content-Type": self.content_type}

    async def json(self, content_type: Any = None) -> Any:
        if self._payload is None:
            raise ValueError("No JSON payload configured")
        return self._payload

    async def text(self) -> str:
        if self._payload is not None:
            import json

            return json.dumps(self._payload)
        if self._body_bytes is not None:
            return self._body_bytes.decode(errors="replace")
        return self._text_body

    async def read(self) -> bytes:
        if self._body_bytes is not None:
            return self._body_bytes
        if self._payload is not None:
            import json

            return json.dumps(self._payload).encode()
        return self._text_body.encode()


class _ResponseContext:
    def __init__(self, response: _MockResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _MockResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _MockSession:
    def __init__(self, request_callable) -> None:
        self.closed = False
        self.request = request_callable

    async def close(self) -> None:
        self.closed = True


class FakeAiohttpClientMock:
    """Minimal aiohttp_client_mock-style helper used by tests."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], _MockResponse] = {}
        self.session = _MockSession(self._request)

    def get(
        self,
        url: str,
        *,
        status: int = 200,
        payload: Any = None,
        body: str = "",
        content_type: str | None = None,
        body_bytes: bytes | None = None,
    ) -> None:
        self._routes[("GET", url)] = _MockResponse(
            status=status,
            payload=payload,
            text_body=body,
            content_type=content_type,
            body_bytes=body_bytes,
        )

    def post(
        self,
        url: str,
        *,
        status: int = 200,
        payload: Any = None,
        body: str = "",
        content_type: str | None = None,
        body_bytes: bytes | None = None,
    ) -> None:
        self._routes[("POST", url)] = _MockResponse(
            status=status,
            payload=payload,
            text_body=body,
            content_type=content_type,
            body_bytes=body_bytes,
        )

    def _request(self, method: str, url: str, headers: dict[str, str] | None = None, json: Any = None):
        key = (method.upper(), url)
        response = self._routes.get(key)
        if response is None:
            raise RuntimeError(f"No mocked route for {method} {url}")
        return _ResponseContext(response)


@pytest.fixture
def aiohttp_client_mock() -> FakeAiohttpClientMock:
    return FakeAiohttpClientMock()
