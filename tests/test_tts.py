from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.voicebox.api_client import VoiceboxApiConnectionError
from custom_components.voicebox.tts import VoiceboxTtsProvider


class _FakeClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, str | None]] = []

    async def async_synthesize(self, text: str, voice: str | None, output_path: str | None):
        if self.should_fail:
            raise VoiceboxApiConnectionError("voicebox offline")

        assert output_path is not None
        Path(output_path).write_bytes(b"RIFFMOCKWAV")
        self.calls.append({"text": text, "voice": voice, "output_path": output_path})
        return {"ok": True}


class _FakeCoordinator:
    def __init__(self, client) -> None:
        self.client = client


class _FakeEntry:
    def __init__(self) -> None:
        self.entry_id = "entry-1"
        self.data = {"host": "voicebox.local", "port": 8000}


@pytest.mark.asyncio
async def test_tts_provider_synthesizes_audio_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr("custom_components.voicebox.tts.SAFE_OUTPUT_BASE_DIR", str(tmp_path))
    provider = VoiceboxTtsProvider(_FakeCoordinator(_FakeClient()), _FakeEntry())

    fmt, audio = await provider.async_get_tts_audio(
        "Hello Home Assistant",
        language="en",
        options={"voice": "alloy"},
    )

    assert fmt == "wav"
    assert audio == b"RIFFMOCKWAV"


@pytest.mark.asyncio
async def test_tts_provider_raises_on_empty_message():
    provider = VoiceboxTtsProvider(_FakeCoordinator(_FakeClient()), _FakeEntry())

    with pytest.raises(Exception, match="cannot be empty"):
        await provider.async_get_tts_audio("   ", language="en", options={})


@pytest.mark.asyncio
async def test_tts_provider_surfaces_api_errors(monkeypatch, tmp_path):
    monkeypatch.setattr("custom_components.voicebox.tts.SAFE_OUTPUT_BASE_DIR", str(tmp_path))
    provider = VoiceboxTtsProvider(
        _FakeCoordinator(_FakeClient(should_fail=True)),
        _FakeEntry(),
    )

    with pytest.raises(Exception, match="Voicebox TTS request failed"):
        await provider.async_get_tts_audio("Hello", language="en", options={})
