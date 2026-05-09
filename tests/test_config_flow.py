from __future__ import annotations

import pytest

from custom_components.voicebox import config_flow
from custom_components.voicebox.api_client import VoiceboxApiConnectionError


class _FakeHass:
    pass


@pytest.mark.asyncio
async def test_validate_input_success(monkeypatch, aiohttp_client_mock):
    aiohttp_client_mock.get(
        "http://127.0.0.1:8000/api/status",
        status=200,
        payload={"status": "running"},
    )

    monkeypatch.setattr(
        config_flow,
        "async_get_clientsession",
        lambda hass: aiohttp_client_mock.session,
    )

    await config_flow._async_validate_input(
        _FakeHass(),
        {"host": "127.0.0.1", "port": 8000},
    )


@pytest.mark.asyncio
async def test_validate_input_raises_cannot_connect(monkeypatch):
    class _BrokenSession:
        closed = False

        def request(self, method, url, headers=None, json=None):
            raise VoiceboxApiConnectionError("network down")

    monkeypatch.setattr(
        config_flow,
        "async_get_clientsession",
        lambda hass: _BrokenSession(),
    )

    with pytest.raises(config_flow.CannotConnect):
        await config_flow._async_validate_input(
            _FakeHass(),
            {"host": "127.0.0.1", "port": 8000},
        )


@pytest.mark.asyncio
async def test_validate_input_raises_invalid_response(monkeypatch, aiohttp_client_mock):
    aiohttp_client_mock.get(
        "http://127.0.0.1:8000/api/status",
        status=500,
        payload={"detail": "bad"},
    )

    monkeypatch.setattr(
        config_flow,
        "async_get_clientsession",
        lambda hass: aiohttp_client_mock.session,
    )

    with pytest.raises(config_flow.InvalidResponse):
        await config_flow._async_validate_input(
            _FakeHass(),
            {"host": "127.0.0.1", "port": 8000},
        )


@pytest.mark.asyncio
async def test_user_step_shows_form_on_first_load():
    flow = config_flow.VoiceboxConfigFlow()
    flow.hass = _FakeHass()

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_user_step_creates_entry_on_valid_input(monkeypatch):
    flow = config_flow.VoiceboxConfigFlow()
    flow.hass = _FakeHass()

    async def _ok_validate(hass, user_input):
        return None

    monkeypatch.setattr(config_flow, "_async_validate_input", _ok_validate)

    result = await flow.async_step_user({"host": "voicebox.local", "port": 9999})

    assert result["type"] == "create_entry"
    assert result["title"] == "Voicebox (voicebox.local:9999)"
    assert result["data"] == {
        "host": "voicebox.local",
        "port": 9999,
        "use_ssl": False,
    }


@pytest.mark.asyncio
async def test_user_step_sets_cannot_connect_error(monkeypatch):
    flow = config_flow.VoiceboxConfigFlow()
    flow.hass = _FakeHass()

    async def _fail_validate(hass, user_input):
        raise config_flow.CannotConnect()

    monkeypatch.setattr(config_flow, "_async_validate_input", _fail_validate)

    result = await flow.async_step_user({"host": "voicebox.local", "port": 9999})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_step_sets_invalid_response_error(monkeypatch):
    flow = config_flow.VoiceboxConfigFlow()
    flow.hass = _FakeHass()

    async def _fail_validate(hass, user_input):
        raise config_flow.InvalidResponse()

    monkeypatch.setattr(config_flow, "_async_validate_input", _fail_validate)

    result = await flow.async_step_user({"host": "voicebox.local", "port": 9999})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_response"}
