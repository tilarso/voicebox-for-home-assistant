"""Switch entities for Voicebox."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api_client import VoiceboxApiError
from .const import DOMAIN
from .coordinator import VoiceboxCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voicebox switch entities from a config entry."""
    coordinator: VoiceboxCoordinator = entry.runtime_data
    async_add_entities([VoiceboxEnabledSwitch(coordinator, entry)])


class VoiceboxEnabledSwitch(CoordinatorEntity[VoiceboxCoordinator], SwitchEntity):
    """Enable/disable control for Voicebox."""

    _attr_has_entity_name = True
    _attr_name = "enabled"
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator: VoiceboxCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_enabled"

    @property
    def is_on(self) -> bool:
        """Return whether Voicebox is currently enabled."""
        data: dict[str, Any] = self.coordinator.data or {}
        if "enabled" in data:
            return bool(data["enabled"])
        status = str(data.get("status", "")).lower()
        return status in {"running", "enabled", "on"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Voicebox."""
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Voicebox."""
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        """Send enable/disable state to Voicebox and refresh coordinator."""
        try:
            response = await self.coordinator.client.async_set_enabled(enabled)
        except VoiceboxApiError:
            await self.coordinator.async_request_refresh()
            raise

        if isinstance(response, dict):
            merged = {**(self.coordinator.data or {}), **response}
            if "enabled" not in merged:
                merged["enabled"] = enabled
            self.coordinator.async_set_updated_data(merged)
        else:
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the parent Voicebox device."""
        host = self._entry.data.get("host", "unknown")
        port = self._entry.data.get("port", "unknown")
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"Voicebox ({host}:{port})",
            manufacturer="Voicebox",
            model="Voicebox API",
        )
