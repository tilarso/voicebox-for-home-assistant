from __future__ import annotations

import asyncio
import types

import aiohttp
import pytest

from custom_components.voicebox.api_client import (
    VoiceboxApiAuthError,
    VoiceboxApiClient,
    VoiceboxApiConnectionError,
    VoiceboxApiResponseError,
)


@pytest.mark.asyncio
async def test_async_status_returns_json_dict(aiohttp_client_mock):
    aiohttp_client_mock.get(
        "http://voicebox.local/api/status",
        status=200,
        payload={"status": "running"},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    result = await client.async_status()

    assert result["status"] == "running"
    assert result["enabled"] is True


@pytest.mark.asyncio
async def test_async_set_enabled_routes_to_enable_and_disable(aiohttp_client_mock):
    aiohttp_client_mock.post(
        "http://voicebox.local/api/enable",
        status=200,
        payload={"enabled": True},
    )
    aiohttp_client_mock.post(
        "http://voicebox.local/api/disable",
        status=200,
        payload={"enabled": False},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    enabled_result = await client.async_set_enabled(True)
    disabled_result = await client.async_set_enabled(False)

    assert enabled_result == {"enabled": True}
    assert disabled_result == {"enabled": False}


@pytest.mark.asyncio
async def test_async_synthesize_posts_expected_payload(aiohttp_client_mock):
    aiohttp_client_mock.post(
        "http://voicebox.local/api/synthesize",
        status=200,
        payload={"ok": True, "file": "/tmp/audio.wav"},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    result = await client.async_synthesize(
        "hello world",
        voice="alloy",
        output_path="/tmp/audio.wav",
    )

    assert result["ok"] is True


@pytest.mark.asyncio
async def test_auth_errors_raise_voicebox_api_auth_error(aiohttp_client_mock):
    aiohttp_client_mock.get(
        "http://voicebox.local/api/status",
        status=401,
        payload={"detail": "unauthorized"},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    with pytest.raises(VoiceboxApiAuthError) as exc:
        await client.async_status()

    assert exc.value.status_code == 401
    assert exc.value.body == {"detail": "unauthorized"}


@pytest.mark.asyncio
async def test_non_2xx_raises_voicebox_api_response_error(aiohttp_client_mock):
    aiohttp_client_mock.post(
        "http://voicebox.local/api/restart",
        status=500,
        payload={"detail": "server error"},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    with pytest.raises(VoiceboxApiResponseError) as exc:
        await client.async_restart()

    assert exc.value.status_code == 500
    assert exc.value.body == {"detail": "server error"}


@pytest.mark.asyncio
async def test_non_json_content_type_returns_text_body_in_response_error(aiohttp_client_mock):
    aiohttp_client_mock.post(
        "http://voicebox.local/api/restart",
        status=500,
        body="upstream exploded",
        content_type="text/plain",
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    with pytest.raises(VoiceboxApiResponseError) as exc:
        await client.async_restart()

    assert exc.value.status_code == 500
    assert exc.value.body == "upstream exploded"


@pytest.mark.asyncio
async def test_network_error_raises_connection_error():
    def _raise(*args, **kwargs):
        raise aiohttp.ClientError("boom")

    session = types.SimpleNamespace(request=_raise, closed=False)
    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiConnectionError):
        await client.async_disable()


@pytest.mark.asyncio
async def test_timeout_error_raises_connection_error():
    def _raise(*args, **kwargs):
        raise asyncio.TimeoutError()

    session = types.SimpleNamespace(request=_raise, closed=False)
    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiConnectionError):
        await client.async_enable()


@pytest.mark.asyncio
async def test_status_falls_back_to_health_for_newer_api(aiohttp_client_mock):
    aiohttp_client_mock.get(
        "http://voicebox.local/api/status",
        status=200,
        body="<!doctype html><html>Not API</html>",
        content_type="text/html",
    )
    aiohttp_client_mock.get(
        "http://voicebox.local/health",
        status=200,
        payload={"status": "healthy", "model_loaded": False},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    result = await client.async_status()

    assert result["status"] == "running"
    assert result["enabled"] is True


@pytest.mark.asyncio
async def test_status_falls_back_to_models_status_when_health_missing(aiohttp_client_mock):
    aiohttp_client_mock.get("http://voicebox.local/api/status", status=404, payload={"detail": "not found"})
    aiohttp_client_mock.get("http://voicebox.local/health", status=404, payload={"detail": "not found"})
    aiohttp_client_mock.get(
        "http://voicebox.local/models/status",
        status=200,
        payload={"model_loaded": False, "model_name": None},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    result = await client.async_status()

    assert result["status"] == "idle"
    assert result["enabled"] is False


@pytest.mark.asyncio
async def test_non_dict_json_response_raises_response_error(aiohttp_client_mock):
    aiohttp_client_mock.get(
        "http://voicebox.local/api/status",
        status=200,
        payload=["not", "a", "dict"],
    )
    aiohttp_client_mock.get(
        "http://voicebox.local/health",
        status=404,
        payload={"detail": "not found"},
    )
    aiohttp_client_mock.get(
        "http://voicebox.local/models/status",
        status=404,
        payload={"detail": "not found"},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    with pytest.raises(VoiceboxApiResponseError) as exc:
        await client.async_status()

    assert "status endpoint validation failed" in str(exc.value)


@pytest.mark.asyncio
async def test_synthesize_falls_back_to_generate_when_legacy_missing(aiohttp_client_mock):
    aiohttp_client_mock.post(
        "http://voicebox.local/api/synthesize",
        status=404,
        payload={"detail": "not found"},
    )
    aiohttp_client_mock.post(
        "http://voicebox.local/generate",
        status=200,
        payload={"generation_id": "abc123", "status": "queued"},
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    result = await client.async_synthesize("hello")

    assert result["generation_id"] == "abc123"


@pytest.mark.asyncio
async def test_synthesize_falls_back_to_speak_and_downloads_audio(aiohttp_client_mock, tmp_path):
    out = tmp_path / "voicebox.wav"

    aiohttp_client_mock.post(
        "http://voicebox.local/api/synthesize",
        status=405,
        payload={"detail": "method not allowed"},
    )
    aiohttp_client_mock.post(
        "http://voicebox.local/generate",
        status=422,
        payload={"detail": "missing profile_id"},
    )
    aiohttp_client_mock.post(
        "http://voicebox.local/speak",
        status=200,
        payload={"id": "gen-1", "status": "generating"},
    )
    aiohttp_client_mock.get(
        "http://voicebox.local/generate/gen-1/status",
        status=200,
        body='data: {"id":"gen-1","status":"completed"}\n\n',
        content_type="text/event-stream",
    )
    aiohttp_client_mock.get(
        "http://voicebox.local/audio/gen-1",
        status=200,
        body_bytes=b"RIFFMOCK",
        content_type="audio/x-wav",
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    result = await client.async_synthesize("hello", voice="T.A.R.S", output_path=str(out))

    assert result["id"] == "gen-1"
    assert result["output_path"] == str(out)
    assert out.read_bytes() == b"RIFFMOCK"


@pytest.mark.asyncio
async def test_synthesize_raises_on_speak_failure_status(aiohttp_client_mock, tmp_path):
    out = tmp_path / "voicebox.wav"

    aiohttp_client_mock.post(
        "http://voicebox.local/api/synthesize",
        status=404,
        payload={"detail": "not found"},
    )
    aiohttp_client_mock.post(
        "http://voicebox.local/generate",
        status=422,
        payload={"detail": "missing profile_id"},
    )
    aiohttp_client_mock.post(
        "http://voicebox.local/speak",
        status=200,
        payload={"id": "gen-fail", "status": "generating"},
    )
    aiohttp_client_mock.get(
        "http://voicebox.local/generate/gen-fail/status",
        status=200,
        body='data: {"id":"gen-fail","status":"failed","error":"boom"}\n\n',
        content_type="text/event-stream",
    )

    client = VoiceboxApiClient("http://voicebox.local", session=aiohttp_client_mock.session)

    with pytest.raises(VoiceboxApiResponseError, match="failed"):
        await client.async_synthesize("hello", output_path=str(out))


@pytest.mark.asyncio
async def test_bearer_token_is_attached_when_api_key_present(monkeypatch, aiohttp_client_mock):
    captured_headers: dict[str, str] = {}
    original_request = aiohttp_client_mock.session.request

    def _capture_request(method, url, headers=None, json=None):
        captured_headers.update(headers or {})
        return original_request(method, url, headers=headers, json=json)

    aiohttp_client_mock.session.request = _capture_request
    aiohttp_client_mock.get(
        "http://voicebox.local/api/status",
        status=200,
        payload={"status": "running"},
    )

    client = VoiceboxApiClient(
        "http://voicebox.local",
        api_key="secret-token",
        session=aiohttp_client_mock.session,
    )

    await client.async_status()

    assert captured_headers["Authorization"] == "Bearer secret-token"
