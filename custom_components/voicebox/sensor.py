"""Sensor entities for Voicebox."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_STATUS, DOMAIN
from .coordinator import VoiceboxCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voicebox sensor entities from a config entry."""
    coordinator: VoiceboxCoordinator = entry.runtime_data
    async_add_entities([VoiceboxStatusSensor(coordinator, entry)])


class VoiceboxStatusSensor(CoordinatorEntity[VoiceboxCoordinator], SensorEntity):
    """Represents the current Voicebox status."""

    _attr_has_entity_name = True
    _attr_name = "status"
    _attr_icon = "mdi:state-machine"

    def __init__(self, coordinator: VoiceboxCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        """Return the current Voicebox status."""
        data: dict[str, Any] = self.coordinator.data or {}
        return str(data.get("status", DEFAULT_STATUS))

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
