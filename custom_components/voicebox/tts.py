"""TTS platform support for Voicebox."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import VoiceboxApiError
from .const import DOMAIN, SAFE_OUTPUT_BASE_DIR
from .coordinator import VoiceboxCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voicebox TTS entities from a config entry."""
    coordinator: VoiceboxCoordinator = entry.runtime_data
    async_add_entities([VoiceboxTtsProvider(coordinator, entry)])


class VoiceboxTtsProvider(TextToSpeechEntity):
    """Voicebox-backed native TTS provider."""

    _attr_has_entity_name = True
    _attr_name = "voicebox"

    def __init__(self, coordinator: VoiceboxCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tts"

    @property
    def default_language(self) -> str:
        """Return default language for generated audio."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported language options."""
        return ["en"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return parent Voicebox device metadata."""
        host = self._entry.data.get("host", "unknown")
        port = self._entry.data.get("port", "unknown")
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Voicebox ({host}:{port})",
            manufacturer="Voicebox",
            model="Voicebox API",
        )

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> tuple[str, bytes] | None:
        """Generate TTS audio via Voicebox and return audio bytes."""
        text = message.strip()
        if not text:
            raise HomeAssistantError("Voicebox TTS message cannot be empty")

        options = options or {}
        voice = options.get("voice")

        audio_dir = Path(SAFE_OUTPUT_BASE_DIR)
        filename = (
            f"tts_{self._entry.entry_id}_"
            f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex}.wav"
        )
        output_path = audio_dir / filename

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            await self._coordinator.client.async_synthesize(
                text=text,
                voice=str(voice) if voice is not None else None,
                output_path=str(output_path),
            )
            audio_bytes = output_path.read_bytes()
        except VoiceboxApiError as err:
            _LOGGER.error("Voicebox TTS request failed for entry %s: %s", self._entry.entry_id, err)
            raise HomeAssistantError(f"Voicebox TTS request failed: {err}") from err
        except OSError as err:
            _LOGGER.error("Voicebox TTS file I/O failed for %s: %s", output_path, err)
            raise HomeAssistantError(f"Voicebox TTS audio file error: {err}") from err

        if not audio_bytes:
            msg = f"Voicebox TTS returned an empty audio file at {output_path}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg)

        return ("wav", audio_bytes)
