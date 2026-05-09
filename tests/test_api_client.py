import asyncio
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from custom_components.voicebox.api_client import (
    VoiceboxApiAuthError,
    VoiceboxApiClient,
    VoiceboxApiConnectionError,
    VoiceboxApiResponseError,
)


class _ResponseCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _response(
    *,
    status=200,
    content_type="application/json",
    json_body=None,
    text_body="",
):
    response = Mock()
    response.status = status
    response.content_type = content_type
    response.json = AsyncMock(return_value={} if json_body is None else json_body)
    response.text = AsyncMock(return_value=text_body)
    return response


@pytest.mark.asyncio
async def test_async_status_returns_json_dict():
    response = _response(json_body={"status": "running"})
    session = Mock(closed=False)
    session.request = Mock(return_value=_ResponseCtx(response))

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    result = await client.async_status()

    assert result == {"status": "running"}
    session.request.assert_called_once_with(
        "GET",
        "http://voicebox.local/api/status",
        headers={"Accept": "application/json"},
        json=None,
    )


@pytest.mark.asyncio
async def test_async_set_enabled_routes_to_enable_and_disable():
    response_enable = _response(json_body={"enabled": True})
    response_disable = _response(json_body={"enabled": False})
    session = Mock(closed=False)
    session.request = Mock(
        side_effect=[_ResponseCtx(response_enable), _ResponseCtx(response_disable)]
    )

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    enabled_result = await client.async_set_enabled(True)
    disabled_result = await client.async_set_enabled(False)

    assert enabled_result == {"enabled": True}
    assert disabled_result == {"enabled": False}


@pytest.mark.asyncio
async def test_async_synthesize_posts_expected_payload():
    response = _response(json_body={"ok": True, "file": "/tmp/audio.wav"})
    session = Mock(closed=False)
    session.request = Mock(return_value=_ResponseCtx(response))

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    result = await client.async_synthesize(
        "hello world",
        voice="alloy",
        output_path="/tmp/audio.wav",
    )

    assert result["ok"] is True
    session.request.assert_called_once_with(
        "POST",
        "http://voicebox.local/api/synthesize",
        headers={"Accept": "application/json"},
        json={
            "text": "hello world",
            "voice": "alloy",
            "output_path": "/tmp/audio.wav",
        },
    )


@pytest.mark.asyncio
async def test_auth_errors_raise_voicebox_api_auth_error():
    response = _response(status=401, json_body={"detail": "unauthorized"})
    session = Mock(closed=False)
    session.request = Mock(return_value=_ResponseCtx(response))

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiAuthError) as exc:
        await client.async_status()

    assert exc.value.status_code == 401
    assert exc.value.body == {"detail": "unauthorized"}


@pytest.mark.asyncio
async def test_non_2xx_raises_voicebox_api_response_error():
    response = _response(status=500, json_body={"detail": "server error"})
    session = Mock(closed=False)
    session.request = Mock(return_value=_ResponseCtx(response))

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiResponseError) as exc:
        await client.async_restart()

    assert exc.value.status_code == 500
    assert exc.value.body == {"detail": "server error"}


@pytest.mark.asyncio
async def test_network_error_raises_connection_error():
    session = Mock(closed=False)
    session.request = Mock(side_effect=aiohttp.ClientError("boom"))

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiConnectionError):
        await client.async_disable()


@pytest.mark.asyncio
async def test_timeout_error_raises_connection_error():
    session = Mock(closed=False)
    session.request = Mock(side_effect=asyncio.TimeoutError())

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiConnectionError):
        await client.async_enable()


@pytest.mark.asyncio
async def test_non_dict_json_response_raises_response_error():
    response = _response(json_body=["not", "a", "dict"])
    session = Mock(closed=False)
    session.request = Mock(return_value=_ResponseCtx(response))

    client = VoiceboxApiClient("http://voicebox.local", session=session)

    with pytest.raises(VoiceboxApiResponseError) as exc:
        await client.async_status()

    assert "non-object JSON" in str(exc.value)


@pytest.mark.asyncio
async def test_bearer_token_is_attached_when_api_key_present():
    response = _response(json_body={"status": "running"})
    session = Mock(closed=False)
    session.request = Mock(return_value=_ResponseCtx(response))

    client = VoiceboxApiClient(
        "http://voicebox.local",
        api_key="secret-token",
        session=session,
    )

    await client.async_status()

    _, _, kwargs = session.request.mock_calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"
