"""The Voicebox integration."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from .const import (
    ATTR_ENTRY_ID,
    ATTR_OUTPUT_PATH,
    ATTR_TEXT,
    ATTR_VOICE,
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USE_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_USE_SSL,
    DOMAIN,
    PLATFORMS,
    SAFE_OUTPUT_BASE_DIR,
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
            vol.Optional(ATTR_ENTRY_ID): str,
        }
    )


def _build_base_url(host: str, port: int, use_ssl: bool) -> str:
    """Build Voicebox base URL from entry configuration."""
    scheme = "https" if use_ssl else "http"
    return f"{scheme}://{host}:{port}"


def _validate_output_path(output_path: str) -> str:
    """Validate output_path is constrained to a safe allowlisted directory."""
    normalized = output_path.strip()
    if not normalized:
        raise ValueError("Service field 'output_path' cannot be empty")
    if "\x00" in normalized:
        raise ValueError("Service field 'output_path' contains an invalid null byte")

    candidate = PurePosixPath(normalized)
    base_dir = PurePosixPath(SAFE_OUTPUT_BASE_DIR)

    if not candidate.is_absolute():
        raise ValueError(
            f"Service field 'output_path' must be absolute and under {SAFE_OUTPUT_BASE_DIR}"
        )
    if ".." in candidate.parts:
        raise ValueError("Service field 'output_path' cannot contain path traversal segments")

    if not (candidate == base_dir or base_dir in candidate.parents):
        raise ValueError(
            f"Service field 'output_path' must stay inside {SAFE_OUTPUT_BASE_DIR}"
        )

    return str(candidate)


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    """Set up Voicebox from a config entry."""
    from homeassistant.core import ServiceCall
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .api_client import VoiceboxApiClient
    from .coordinator import VoiceboxCoordinator

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    use_ssl = bool(entry.data.get(CONF_USE_SSL, DEFAULT_USE_SSL))

    client = VoiceboxApiClient(
        base_url=_build_base_url(host=host, port=port, use_ssl=use_ssl),
        api_key=entry.data.get(CONF_API_KEY),
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

        target_entry_id = call.data.get(ATTR_ENTRY_ID)
        if target_entry_id is not None:
            selected_coordinator = active_coordinators.get(str(target_entry_id))
            if selected_coordinator is None:
                raise ServiceValidationError(
                    f"Voicebox entry '{target_entry_id}' is not configured"
                )
        elif len(active_coordinators) == 1:
            selected_coordinator = next(iter(active_coordinators.values()))
        else:
            configured_entries = ", ".join(sorted(active_coordinators.keys()))
            raise ServiceValidationError(
                "Multiple Voicebox instances are configured; include 'entry_id' in service data. "
                f"Available entry_ids: {configured_entries}"
            )

        text = str(call.data[ATTR_TEXT]).strip()
        if not text:
            raise ServiceValidationError("Service field 'text' cannot be empty")

        voice = call.data.get(ATTR_VOICE)
        raw_output_path = call.data.get(ATTR_OUTPUT_PATH)
        output_path = None
        if raw_output_path is not None:
            try:
                output_path = _validate_output_path(str(raw_output_path))
            except ValueError as err:
                raise ServiceValidationError(str(err)) from err

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
