from __future__ import annotations

import pytest

from custom_components.voicebox import config_flow
from custom_components.voicebox.api_client import VoiceboxApiConnectionError


class _FakeHass:
    pass


@pytest.mark.parametrize(
    "host",
    [
        "voicebox.local",
        "voicebox",
        "voicebox-1.internal",
        "192.168.1.10",
        "10.0.0.8",
    ],
)
def test_validate_host_accepts_valid_values(host):
    config_flow._validate_host(host)


@pytest.mark.parametrize(
    "host",
    [
        "",
        "localhost",
        "localhost.localdomain",
        "127.0.0.1",
        "169.254.1.2",
        "0.1.2.3",
        "::1",
        "[::1]",
        "http://voicebox.local",
        "voicebox.local/path",
        "voicebox.local?x=1",
        "voicebox.local#frag",
        "voicebox..local",
        "-voicebox.local",
        "voicebox-.local",
        "voicebox_local.local",
        "224.0.0.1",
        "240.0.0.1",
    ],
)
def test_validate_host_rejects_invalid_values(host):
    with pytest.raises(config_flow.InvalidHost):
        config_flow._validate_host(host)


def test_normalize_user_input_trims_lowercases_and_omits_blank_api_key():
    normalized = config_flow._normalize_user_input(
        {
            "host": "  VoiceBox.LOCAL  ",
            "port": "8000",
            "api_key": "   ",
            "use_ssl": False,
        }
    )

    assert normalized == {
        "host": "voicebox.local",
        "port": 8000,
        "use_ssl": False,
    }


def test_normalize_user_input_trims_api_key_when_present():
    normalized = config_flow._normalize_user_input(
        {
            "host": "voicebox.local",
            "port": 8000,
            "api_key": "  topsecret  ",
            "use_ssl": True,
        }
    )

    assert normalized == {
        "host": "voicebox.local",
        "port": 8000,
        "api_key": "topsecret",
        "use_ssl": True,
    }


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
async def test_validate_input_uses_https_base_url_when_ssl_enabled(monkeypatch):
    captured: dict[str, object] = {}

    class _CapturingClient:
        def __init__(self, *, base_url, api_key, session, request_timeout):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["session"] = session
            captured["request_timeout"] = request_timeout

        async def async_status(self):
            return {"status": "running"}

    monkeypatch.setattr(config_flow, "VoiceboxApiClient", _CapturingClient)
    monkeypatch.setattr(config_flow, "async_get_clientsession", lambda hass: object())

    await config_flow._async_validate_input(
        _FakeHass(),
        {
            "host": "voicebox.local",
            "port": 8443,
            "use_ssl": True,
            "api_key": "secret",
        },
    )

    assert captured["base_url"] == "https://voicebox.local:8443"
    assert captured["api_key"] == "secret"
    assert captured["request_timeout"] == config_flow.DEFAULT_TIMEOUT


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
async def test_user_step_normalizes_host_unique_id_title_and_api_key(monkeypatch):
    flow = config_flow.VoiceboxConfigFlow()
    flow.hass = _FakeHass()
    captured: dict[str, str] = {}

    async def _ok_validate(hass, user_input):
        return None

    async def _capture_unique_id(unique_id: str) -> None:
        captured["unique_id"] = unique_id

    monkeypatch.setattr(config_flow, "_async_validate_input", _ok_validate)
    monkeypatch.setattr(flow, "async_set_unique_id", _capture_unique_id)
    monkeypatch.setattr(flow, "_abort_if_unique_id_configured", lambda: None)

    result = await flow.async_step_user(
        {
            "host": "  VoiceBox.LOCAL  ",
            "port": "8000",
            "api_key": "  secret-key  ",
            "use_ssl": True,
        }
    )

    assert captured["unique_id"] == "voicebox.local:8000"
    assert result["type"] == "create_entry"
    assert result["title"] == "Voicebox (voicebox.local:8000)"
    assert result["data"] == {
        "host": "voicebox.local",
        "port": 8000,
        "api_key": "secret-key",
        "use_ssl": True,
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
