"""The Voicebox integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DEFAULT_TIMEOUT, PLATFORMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up Voicebox from a config entry."""
    from homeassistant.const import CONF_HOST, CONF_PORT
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .api_client import VoiceboxApiClient
    from .coordinator import VoiceboxCoordinator

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    client = VoiceboxApiClient(
        base_url=f"http://{host}:{port}",
        api_key=entry.data.get("api_key"),
        session=async_get_clientsession(hass),
        request_timeout=DEFAULT_TIMEOUT,
    )

    coordinator = VoiceboxCoordinator(hass, client, entry.entry_id)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator: VoiceboxCoordinator | None = getattr(entry, "runtime_data", None)
    if unload_ok and coordinator is not None:
        await coordinator.client.async_close()

    return unload_ok
