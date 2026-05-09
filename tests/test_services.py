import sys
import types
from unittest.mock import AsyncMock

import pytest

from custom_components.voicebox import async_setup_entry, async_unload_entry
from custom_components.voicebox.const import (
    ATTR_OUTPUT_PATH,
    ATTR_TEXT,
    ATTR_VOICE,
    DOMAIN,
    SERVICE_SYNTHESIZE,
)


@pytest.fixture(autouse=True)
def _install_stubs(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")

    const_mod = types.ModuleType("homeassistant.const")
    const_mod.CONF_HOST = "host"
    const_mod.CONF_PORT = "port"

    core_mod = types.ModuleType("homeassistant.core")

    class ServiceCall:
        def __init__(self, data):
            self.data = data

    core_mod.ServiceCall = ServiceCall

    exceptions_mod = types.ModuleType("homeassistant.exceptions")

    class ServiceValidationError(Exception):
        pass

    exceptions_mod.ServiceValidationError = ServiceValidationError

    helpers_mod = types.ModuleType("homeassistant.helpers")
    aiohttp_client_mod = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client_mod.async_get_clientsession = lambda hass: object()

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.const", const_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.aiohttp_client", aiohttp_client_mod)

    voluptuous_mod = types.ModuleType("voluptuous")

    def _identity(*args, **kwargs):
        if args:
            return args[0]
        return lambda value: value

    class _Length:
        def __init__(self, min=None, max=None):
            self.min = min
            self.max = max

        def __call__(self, value):
            return value

    class _Schema:
        def __init__(self, schema):
            self.schema = schema

        def __call__(self, value):
            return value

    voluptuous_mod.Required = _identity
    voluptuous_mod.Optional = _identity
    voluptuous_mod.All = _identity
    voluptuous_mod.Length = _Length
    voluptuous_mod.Schema = _Schema
    monkeypatch.setitem(sys.modules, "voluptuous", voluptuous_mod)

    api_client_mod = types.ModuleType("custom_components.voicebox.api_client")

    class VoiceboxApiClient:
        def __init__(self, base_url, api_key=None, session=None, request_timeout=10):
            self.base_url = base_url
            self.api_key = api_key
            self.session = session
            self.request_timeout = request_timeout
            self.async_synthesize = AsyncMock(return_value={"ok": True})
            self.async_close = AsyncMock()

    api_client_mod.VoiceboxApiClient = VoiceboxApiClient
    monkeypatch.setitem(sys.modules, "custom_components.voicebox.api_client", api_client_mod)

    coordinator_mod = types.ModuleType("custom_components.voicebox.coordinator")

    class VoiceboxCoordinator:
        def __init__(self, hass, client, entry_id):
            self.hass = hass
            self.client = client
            self.entry_id = entry_id
            self.data = {}

        async def async_config_entry_first_refresh(self):
            return None

    coordinator_mod.VoiceboxCoordinator = VoiceboxCoordinator
    monkeypatch.setitem(sys.modules, "custom_components.voicebox.coordinator", coordinator_mod)


class _ServiceRegistry:
    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], object] = {}

    def has_service(self, domain: str, service: str) -> bool:
        return (domain, service) in self._handlers

    def async_register(self, domain: str, service: str, handler, schema=None) -> None:
        self._handlers[(domain, service)] = {"handler": handler, "schema": schema}

    def async_remove(self, domain: str, service: str) -> None:
        self._handlers.pop((domain, service), None)

    def get_handler(self, domain: str, service: str):
        return self._handlers[(domain, service)]["handler"]


class _ConfigEntries:
    async def async_forward_entry_setups(self, entry, platforms) -> None:
        return None

    async def async_unload_platforms(self, entry, platforms) -> bool:
        return True


class _FakeHass:
    def __init__(self) -> None:
        self.data = {}
        self.services = _ServiceRegistry()
        self.config_entries = _ConfigEntries()


class _FakeEntry:
    def __init__(self) -> None:
        self.entry_id = "entry-1"
        self.data = {"host": "127.0.0.1", "port": 8000}
        self.runtime_data = None


class _FakeServiceCall:
    def __init__(self, data):
        self.data = data


@pytest.mark.asyncio
async def test_setup_registers_synthesize_service():
    hass = _FakeHass()
    entry = _FakeEntry()

    ok = await async_setup_entry(hass, entry)

    assert ok is True
    assert hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE)
    assert entry.runtime_data is not None


@pytest.mark.asyncio
async def test_synthesize_service_passes_payload_to_client():
    hass = _FakeHass()
    entry = _FakeEntry()

    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)
    call = _FakeServiceCall(
        {
            ATTR_TEXT: "Hello from test",
            ATTR_VOICE: "alloy",
            ATTR_OUTPUT_PATH: "/tmp/voice.wav",
        }
    )

    await handler(call)

    entry.runtime_data.client.async_synthesize.assert_awaited_once_with(
        text="Hello from test",
        voice="alloy",
        output_path="/tmp/voice.wav",
    )


@pytest.mark.asyncio
async def test_unload_removes_service_when_last_entry():
    hass = _FakeHass()
    entry = _FakeEntry()

    await async_setup_entry(hass, entry)
    assert hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE)

    ok = await async_unload_entry(hass, entry)

    assert ok is True
    assert not hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE)
    entry.runtime_data.client.async_close.assert_awaited_once()
