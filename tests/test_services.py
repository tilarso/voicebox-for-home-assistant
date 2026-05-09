import sys
import types
from unittest.mock import AsyncMock

import pytest

from custom_components.voicebox import async_setup_entry, async_unload_entry
from custom_components.voicebox.const import (
    ATTR_ENTRY_ID,
    ATTR_OUTPUT_PATH,
    ATTR_TEXT,
    ATTR_VOICE,
    DOMAIN,
    SERVICE_SYNTHESIZE,
)


@pytest.fixture(autouse=True)
def _install_stubs(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")

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
    def __init__(self, entry_id: str, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.entry_id = entry_id
        self.data = {"host": host, "port": port, "use_ssl": False, "api_key": "key"}
        self.runtime_data = None


class _FakeServiceCall:
    def __init__(self, data):
        self.data = data


@pytest.mark.asyncio
async def test_setup_registers_synthesize_service():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")

    ok = await async_setup_entry(hass, entry)

    assert ok is True
    assert hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE)
    assert entry.runtime_data is not None


@pytest.mark.asyncio
async def test_synthesize_service_passes_payload_to_selected_entry():
    hass = _FakeHass()
    entry_one = _FakeEntry("entry-1", host="voicebox1.local")
    entry_two = _FakeEntry("entry-2", host="voicebox2.local")

    await async_setup_entry(hass, entry_one)
    await async_setup_entry(hass, entry_two)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)
    call = _FakeServiceCall(
        {
            ATTR_TEXT: "Hello from test",
            ATTR_VOICE: "alloy",
            ATTR_OUTPUT_PATH: "/config/media/voicebox/audio.wav",
            ATTR_ENTRY_ID: "entry-2",
        }
    )

    await handler(call)

    entry_one.runtime_data.client.async_synthesize.assert_not_called()
    entry_two.runtime_data.client.async_synthesize.assert_awaited_once_with(
        text="Hello from test",
        voice="alloy",
        output_path="/config/media/voicebox/audio.wav",
    )


@pytest.mark.asyncio
async def test_synthesize_with_multiple_entries_requires_entry_id():
    hass = _FakeHass()
    entry_one = _FakeEntry("entry-1")
    entry_two = _FakeEntry("entry-2")

    await async_setup_entry(hass, entry_one)
    await async_setup_entry(hass, entry_two)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    with pytest.raises(Exception, match="Multiple Voicebox instances are configured"):
        await handler(_FakeServiceCall({ATTR_TEXT: "hello"}))


@pytest.mark.asyncio
async def test_synthesize_rejects_output_path_outside_allowlist():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")
    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    with pytest.raises(Exception, match="must stay inside /config/media/voicebox"):
        await handler(_FakeServiceCall({ATTR_TEXT: "hello", ATTR_OUTPUT_PATH: "/etc/passwd"}))


@pytest.mark.asyncio
async def test_synthesize_rejects_relative_output_path():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")
    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    with pytest.raises(Exception, match="must be absolute"):
        await handler(_FakeServiceCall({ATTR_TEXT: "hello", ATTR_OUTPUT_PATH: "voicebox.wav"}))


@pytest.mark.asyncio
async def test_synthesize_rejects_traversal_output_path():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")
    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    with pytest.raises(Exception, match="cannot contain path traversal"):
        await handler(
            _FakeServiceCall(
                {ATTR_TEXT: "hello", ATTR_OUTPUT_PATH: "/config/media/voicebox/../escape.wav"}
            )
        )


@pytest.mark.asyncio
async def test_synthesize_rejects_null_byte_output_path():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")
    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    with pytest.raises(Exception, match="invalid null byte"):
        await handler(
            _FakeServiceCall({ATTR_TEXT: "hello", ATTR_OUTPUT_PATH: "/config/media/voicebox/a\x00.wav"})
        )


@pytest.mark.asyncio
async def test_synthesize_accepts_base_dir_output_path():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")
    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    await handler(
        _FakeServiceCall({ATTR_TEXT: "hello", ATTR_OUTPUT_PATH: "/config/media/voicebox"})
    )

    entry.runtime_data.client.async_synthesize.assert_awaited_once_with(
        text="hello",
        voice=None,
        output_path="/config/media/voicebox",
    )


@pytest.mark.asyncio
async def test_synthesize_accepts_nested_output_path():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")
    await async_setup_entry(hass, entry)

    handler = hass.services.get_handler(DOMAIN, SERVICE_SYNTHESIZE)

    await handler(
        _FakeServiceCall(
            {ATTR_TEXT: "hello", ATTR_OUTPUT_PATH: "/config/media/voicebox/subdir/audio.wav"}
        )
    )

    entry.runtime_data.client.async_synthesize.assert_awaited_once_with(
        text="hello",
        voice=None,
        output_path="/config/media/voicebox/subdir/audio.wav",
    )


@pytest.mark.asyncio
async def test_setup_uses_https_base_url_when_use_ssl_enabled():
    hass = _FakeHass()
    entry = _FakeEntry("entry-https", host="voicebox.local", port=8443)
    entry.data["use_ssl"] = True

    ok = await async_setup_entry(hass, entry)

    assert ok is True
    assert entry.runtime_data.client.base_url == "https://voicebox.local:8443"


@pytest.mark.asyncio
async def test_unload_removes_service_when_last_entry():
    hass = _FakeHass()
    entry = _FakeEntry("entry-1")

    await async_setup_entry(hass, entry)
    assert hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE)

    ok = await async_unload_entry(hass, entry)

    assert ok is True
    assert not hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE)
    entry.runtime_data.client.async_close.assert_awaited_once()
