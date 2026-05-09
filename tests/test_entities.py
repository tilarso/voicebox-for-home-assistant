from __future__ import annotations

import pytest

from custom_components.voicebox.api_client import VoiceboxApiError
from custom_components.voicebox.sensor import VoiceboxStatusSensor
from custom_components.voicebox.switch import VoiceboxEnabledSwitch


class _FakeClient:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[bool] = []

    async def async_set_enabled(self, enabled: bool):
        self.calls.append(enabled)
        if self._error is not None:
            raise self._error
        return self._response


class _FakeCoordinator:
    def __init__(self, data=None, response=None, error: Exception | None = None) -> None:
        self.data = {} if data is None else data
        self.client = _FakeClient(response=response, error=error)
        self.updated_data = None
        self.refresh_count = 0

    def async_set_updated_data(self, data):
        self.updated_data = data
        self.data = data

    async def async_request_refresh(self):
        self.refresh_count += 1


class _FakeEntry:
    def __init__(self) -> None:
        self.entry_id = "entry-1"
        self.data = {"host": "127.0.0.1", "port": 8000}


def test_status_sensor_uses_status_and_defaults_to_unknown():
    entry = _FakeEntry()

    sensor = VoiceboxStatusSensor(_FakeCoordinator(data={"status": "running"}), entry)
    assert sensor.native_value == "running"

    fallback_sensor = VoiceboxStatusSensor(_FakeCoordinator(data={}), entry)
    assert fallback_sensor.native_value == "unknown"


def test_switch_state_prefers_enabled_then_status_fallback():
    entry = _FakeEntry()

    switch_enabled = VoiceboxEnabledSwitch(_FakeCoordinator(data={"enabled": True}), entry)
    assert switch_enabled.is_on is True

    switch_status = VoiceboxEnabledSwitch(_FakeCoordinator(data={"status": "running"}), entry)
    assert switch_status.is_on is True

    switch_off = VoiceboxEnabledSwitch(_FakeCoordinator(data={"status": "stopped"}), entry)
    assert switch_off.is_on is False


@pytest.mark.asyncio
async def test_switch_turn_on_updates_coordinator_data():
    coordinator = _FakeCoordinator(data={"status": "stopped"}, response={"enabled": True})
    switch = VoiceboxEnabledSwitch(coordinator, _FakeEntry())

    await switch.async_turn_on()

    assert coordinator.client.calls == [True]
    assert coordinator.updated_data["enabled"] is True


@pytest.mark.asyncio
async def test_switch_turn_off_sets_enabled_when_response_missing_field():
    coordinator = _FakeCoordinator(data={"status": "running"}, response={"status": "stopped"})
    switch = VoiceboxEnabledSwitch(coordinator, _FakeEntry())

    await switch.async_turn_off()

    assert coordinator.client.calls == [False]
    assert coordinator.updated_data["enabled"] is False


@pytest.mark.asyncio
async def test_switch_refreshes_and_reraises_on_api_error():
    coordinator = _FakeCoordinator(data={"status": "running"}, error=VoiceboxApiError("boom"))
    switch = VoiceboxEnabledSwitch(coordinator, _FakeEntry())

    with pytest.raises(VoiceboxApiError):
        await switch.async_turn_off()

    assert coordinator.refresh_count == 1
