import importlib
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _install_stubs(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")

    config_entries_mod = types.ModuleType("homeassistant.config_entries")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

        async def async_set_unique_id(self, unique_id):
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            return None

        def async_create_entry(self, *, title, data):
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(self, *, step_id, data_schema, errors):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors,
            }

    config_entries_mod.ConfigFlow = ConfigFlow

    const_mod = types.ModuleType("homeassistant.const")
    const_mod.CONF_HOST = "host"
    const_mod.CONF_PORT = "port"

    core_mod = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    core_mod.HomeAssistant = HomeAssistant

    helpers_mod = types.ModuleType("homeassistant.helpers")
    aiohttp_client_mod = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client_mod.async_get_clientsession = lambda hass: object()

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.config_entries", config_entries_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.const", const_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.aiohttp_client", aiohttp_client_mod)

    voluptuous_mod = types.ModuleType("voluptuous")

    class _Schema:
        def __init__(self, schema):
            self.schema = schema

    def _identity(*args, **kwargs):
        if args:
            return args[0]
        return lambda value: value

    voluptuous_mod.Schema = _Schema
    voluptuous_mod.Required = _identity
    voluptuous_mod.All = _identity
    voluptuous_mod.Coerce = _identity
    voluptuous_mod.Range = _identity
    monkeypatch.setitem(sys.modules, "voluptuous", voluptuous_mod)


@pytest.mark.asyncio
async def test_async_step_user_success_creates_entry(monkeypatch):
    module = importlib.import_module("custom_components.voicebox.config_flow")

    async def _ok_validate(_hass, _data):
        return None

    monkeypatch.setattr(module, "_async_validate_input", _ok_validate)

    flow = module.VoiceboxConfigFlow()
    flow.hass = object()

    result = await flow.async_step_user({"host": "voicebox.local", "port": 8000})

    assert result["type"] == "create_entry"
    assert result["data"] == {"host": "voicebox.local", "port": 8000}
    assert result["title"] == "Voicebox (voicebox.local:8000)"


@pytest.mark.asyncio
async def test_async_step_user_cannot_connect_maps_error(monkeypatch):
    module = importlib.import_module("custom_components.voicebox.config_flow")

    async def _raise_cannot_connect(_hass, _data):
        raise module.CannotConnect

    monkeypatch.setattr(module, "_async_validate_input", _raise_cannot_connect)

    flow = module.VoiceboxConfigFlow()
    flow.hass = object()

    result = await flow.async_step_user({"host": "voicebox.local", "port": 8000})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
