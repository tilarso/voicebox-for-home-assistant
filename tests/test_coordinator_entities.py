import importlib
import sys
import types
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _install_stubs(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")

    core_mod = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    core_mod.HomeAssistant = HomeAssistant

    update_coordinator_mod = types.ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        def __init__(self, hass, logger=None, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = {}

        async def async_request_refresh(self):
            return None

        def async_set_updated_data(self, data):
            self.data = data

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    update_coordinator_mod.UpdateFailed = UpdateFailed
    update_coordinator_mod.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator_mod.CoordinatorEntity = CoordinatorEntity

    sensor_mod = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:
        pass

    sensor_mod.SensorEntity = SensorEntity

    switch_mod = types.ModuleType("homeassistant.components.switch")

    class SwitchEntity:
        pass

    switch_mod.SwitchEntity = SwitchEntity

    config_entries_mod = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        def __init__(self, entry_id="entry-1", data=None):
            self.entry_id = entry_id
            self.data = data or {}
            self.runtime_data = None

    config_entries_mod.ConfigEntry = ConfigEntry

    entity_mod = types.ModuleType("homeassistant.helpers.entity")

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    entity_mod.DeviceInfo = DeviceInfo

    entity_platform_mod = types.ModuleType("homeassistant.helpers.entity_platform")

    class AddEntitiesCallback:
        pass

    entity_platform_mod.AddEntitiesCallback = AddEntitiesCallback

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.update_coordinator", update_coordinator_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.components.sensor", sensor_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.components.switch", switch_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.config_entries", config_entries_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.entity", entity_mod)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.entity_platform", entity_platform_mod)


@pytest.mark.asyncio
async def test_coordinator_defaults_status_when_missing():
    coordinator_mod = importlib.import_module("custom_components.voicebox.coordinator")

    client = types.SimpleNamespace(async_status=AsyncMock(return_value={"enabled": True}))
    coordinator = coordinator_mod.VoiceboxCoordinator(hass=object(), client=client, entry_id="entry-1")

    data = await coordinator._async_update_data()

    assert data["status"] == "unknown"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_coordinator_wraps_api_error_as_update_failed():
    coordinator_mod = importlib.import_module("custom_components.voicebox.coordinator")
    api_mod = importlib.import_module("custom_components.voicebox.api_client")

    client = types.SimpleNamespace(
        async_status=AsyncMock(side_effect=api_mod.VoiceboxApiConnectionError("boom"))
    )
    coordinator = coordinator_mod.VoiceboxCoordinator(hass=object(), client=client, entry_id="entry-1")

    with pytest.raises(Exception, match="boom"):
        await coordinator._async_update_data()


def test_status_sensor_reports_default_and_device_info():
    sensor_mod = importlib.import_module("custom_components.voicebox.sensor")

    coordinator = types.SimpleNamespace(data={})
    entry = types.SimpleNamespace(entry_id="entry-1", data={"host": "voicebox.local", "port": 8000})

    entity = sensor_mod.VoiceboxStatusSensor(coordinator, entry)

    assert entity.native_value == "unknown"
    assert entity.device_info.name == "Voicebox (voicebox.local:8000)"


@pytest.mark.asyncio
async def test_enabled_switch_updates_data_optimistically_on_success():
    switch_mod = importlib.import_module("custom_components.voicebox.switch")

    client = types.SimpleNamespace(async_set_enabled=AsyncMock(return_value={"status": "running"}))

    coordinator = types.SimpleNamespace(
        client=client,
        data={"status": "stopped"},
        async_request_refresh=AsyncMock(),
    )

    def _set_updated_data(data):
        coordinator.data = data

    coordinator.async_set_updated_data = _set_updated_data
    entry = types.SimpleNamespace(entry_id="entry-1", data={"host": "voicebox.local", "port": 8000})

    entity = switch_mod.VoiceboxEnabledSwitch(coordinator, entry)

    await entity.async_turn_on()

    client.async_set_enabled.assert_awaited_once_with(True)
    assert coordinator.data["enabled"] is True
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_enabled_switch_requests_refresh_on_error():
    switch_mod = importlib.import_module("custom_components.voicebox.switch")
    api_mod = importlib.import_module("custom_components.voicebox.api_client")

    client = types.SimpleNamespace(
        async_set_enabled=AsyncMock(side_effect=api_mod.VoiceboxApiConnectionError("fail"))
    )
    coordinator = types.SimpleNamespace(
        client=client,
        data={"status": "running"},
        async_set_updated_data=AsyncMock(),
        async_request_refresh=AsyncMock(),
    )
    entry = types.SimpleNamespace(entry_id="entry-1", data={"host": "voicebox.local", "port": 8000})

    entity = switch_mod.VoiceboxEnabledSwitch(coordinator, entry)

    with pytest.raises(api_mod.VoiceboxApiConnectionError):
        await entity.async_turn_off()

    coordinator.async_request_refresh.assert_awaited_once()
