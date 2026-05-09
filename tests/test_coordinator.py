from __future__ import annotations

import pytest

from custom_components.voicebox.api_client import VoiceboxApiError
from custom_components.voicebox.const import DEFAULT_STATUS
from custom_components.voicebox.coordinator import VoiceboxCoordinator


class _FakeClient:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self._result = {} if result is None else result
        self._error = error

    async def async_status(self):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeHass:
    pass


@pytest.mark.asyncio
async def test_coordinator_returns_status_data():
    coordinator = VoiceboxCoordinator(
        hass=_FakeHass(),
        client=_FakeClient(result={"status": "running", "enabled": True}),
        entry_id="entry-1",
    )

    result = await coordinator._async_update_data()

    assert result == {"status": "running", "enabled": True}


@pytest.mark.asyncio
async def test_coordinator_injects_default_status_when_missing():
    coordinator = VoiceboxCoordinator(
        hass=_FakeHass(),
        client=_FakeClient(result={"enabled": False}),
        entry_id="entry-2",
    )

    result = await coordinator._async_update_data()

    assert result["enabled"] is False
    assert result["status"] == DEFAULT_STATUS


@pytest.mark.asyncio
async def test_coordinator_wraps_api_error_with_update_failed():
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator = VoiceboxCoordinator(
        hass=_FakeHass(),
        client=_FakeClient(error=VoiceboxApiError("boom")),
        entry_id="entry-3",
    )

    try:
        await coordinator._async_update_data()
    except UpdateFailed as err:
        assert "boom" in str(err)
    else:
        raise AssertionError("Expected UpdateFailed")
