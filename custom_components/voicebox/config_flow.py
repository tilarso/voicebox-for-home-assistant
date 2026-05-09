"""Config flow for Voicebox integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import VoiceboxApiClient, VoiceboxApiConnectionError, VoiceboxApiResponseError
from .const import DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN


class VoiceboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Voicebox."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _async_validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            except Exception:  # pragma: no cover
                errors["base"] = "unknown"
            else:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Voicebox ({host}:{port})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT)): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
        )


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate user input allows us to connect."""
    host = str(data[CONF_HOST]).strip()
    port = int(data[CONF_PORT])
    client = VoiceboxApiClient(
        base_url=f"http://{host}:{port}",
        session=async_get_clientsession(hass),
        request_timeout=DEFAULT_TIMEOUT,
    )

    try:
        await client.async_status()
    except VoiceboxApiConnectionError as err:
        raise CannotConnect from err
    except VoiceboxApiResponseError as err:
        raise InvalidResponse from err


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidResponse(Exception):
    """Error to indicate we got an unexpected response from the API."""
