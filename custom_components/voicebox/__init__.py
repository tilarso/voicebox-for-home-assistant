"""The Voicebox integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import (
    ATTR_OUTPUT_PATH,
    ATTR_TEXT,
    ATTR_VOICE,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    SERVICE_SYNTHESIZE,
)

if TYPE_CHECKING:
    import voluptuous as vol
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _build_synthesize_schema() -> "vol.Schema":
    """Create service schema lazily so module import does not require voluptuous."""
    import voluptuous as vol

    return vol.Schema(
        {
            vol.Required(ATTR_TEXT): vol.All(str, vol.Length(min=1)),
            vol.Optional(ATTR_VOICE): str,
            vol.Optional(ATTR_OUTPUT_PATH): str,
        }
    )


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up Voicebox from a config entry."""
    from homeassistant.const import CONF_HOST, CONF_PORT
    from homeassistant.core import ServiceCall
    from homeassistant.exceptions import ServiceValidationError
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

    domain_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    coordinators: dict[str, VoiceboxCoordinator] = domain_data.setdefault("coordinators", {})
    coordinators[entry.entry_id] = coordinator

    async def _handle_synthesize(call: ServiceCall) -> None:
        active_coordinators: dict[str, VoiceboxCoordinator] = hass.data.get(DOMAIN, {}).get(
            "coordinators", {}
        )
        if not active_coordinators:
            raise ServiceValidationError("No configured Voicebox instance is available")

        selected_coordinator = next(iter(active_coordinators.values()))

        text = str(call.data[ATTR_TEXT]).strip()
        if not text:
            raise ServiceValidationError("Service field 'text' cannot be empty")

        voice = call.data.get(ATTR_VOICE)
        output_path = call.data.get(ATTR_OUTPUT_PATH)

        await selected_coordinator.client.async_synthesize(
            text=text,
            voice=voice,
            output_path=output_path,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SYNTHESIZE,
            _handle_synthesize,
            schema=_build_synthesize_schema(),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator: VoiceboxCoordinator | None = getattr(entry, "runtime_data", None)
    if unload_ok and coordinator is not None:
        await coordinator.client.async_close()

    domain_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    coordinators: dict[str, VoiceboxCoordinator] = domain_data.get("coordinators", {})
    coordinators.pop(entry.entry_id, None)

    if not coordinators and hass.services.has_service(DOMAIN, SERVICE_SYNTHESIZE):
        hass.services.async_remove(DOMAIN, SERVICE_SYNTHESIZE)

    return unload_ok
