"""Config flow for Voicebox integration."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_client import (
    VoiceboxApiAuthError,
    VoiceboxApiClient,
    VoiceboxApiConnectionError,
    VoiceboxApiResponseError,
)
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_USE_SSL,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_USE_SSL,
    DOMAIN,
)


class VoiceboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Voicebox."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_input = _normalize_user_input(user_input)
            try:
                _validate_host(normalized_input[CONF_HOST])
                await _async_validate_input(self.hass, normalized_input)
            except InvalidHost:
                errors[CONF_HOST] = "invalid_host"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            except Exception:  # pragma: no cover
                errors["base"] = "unknown"
            else:
                host = normalized_input[CONF_HOST]
                port = normalized_input[CONF_PORT]
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Voicebox ({host}:{port})",
                    data=normalized_input,
                )

        current_values = _normalize_user_input(user_input or {})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_values[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=current_values[CONF_PORT]): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Optional(CONF_API_KEY, default=current_values.get(CONF_API_KEY, "")): str,
                    vol.Optional(CONF_USE_SSL, default=current_values[CONF_USE_SSL]): bool,
                }
            ),
            errors=errors,
        )


def _normalize_user_input(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize config flow user input to canonical values."""
    host = str(data.get(CONF_HOST, "")).strip().lower()
    port = int(data.get(CONF_PORT, DEFAULT_PORT))

    api_key_raw = data.get(CONF_API_KEY)
    api_key = None
    if api_key_raw is not None:
        stripped = str(api_key_raw).strip()
        if stripped:
            api_key = stripped

    use_ssl = bool(data.get(CONF_USE_SSL, DEFAULT_USE_SSL))

    normalized: dict[str, Any] = {
        CONF_HOST: host,
        CONF_PORT: port,
        CONF_USE_SSL: use_ssl,
    }
    if api_key is not None:
        normalized[CONF_API_KEY] = api_key

    return normalized


def _validate_host(host: str) -> None:
    """Validate host input to reduce SSRF risk."""
    if not host:
        raise InvalidHost

    if "://" in host or "/" in host or "?" in host or "#" in host:
        raise InvalidHost

    if host.startswith("[") or host.endswith("]"):
        raise InvalidHost

    if ":" in host:
        raise InvalidHost

    lowered = host.lower()

    blocked_hosts = {"localhost", "localhost.localdomain"}
    if lowered in blocked_hosts:
        raise InvalidHost

    blocked_prefixes = (
        "169.254.",
        "127.",
        "0.",
    )
    if lowered.startswith(blocked_prefixes):
        raise InvalidHost

    try:
        parsed_ip = ip_address(host)
    except ValueError:
        # hostname path
        labels = host.split(".")
        if any(not label for label in labels):
            raise InvalidHost
        allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        for label in labels:
            if label.startswith("-") or label.endswith("-"):
                raise InvalidHost
            if not set(label).issubset(allowed_chars):
                raise InvalidHost
        return

    # IP path
    if (
        parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_multicast
        or parsed_ip.is_unspecified
        or parsed_ip.is_reserved
    ):
        raise InvalidHost


async def _async_validate_input(hass, data: dict[str, Any]) -> None:
    """Validate user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    use_ssl = data.get(CONF_USE_SSL, DEFAULT_USE_SSL)
    api_key = data.get(CONF_API_KEY)

    scheme = "https" if use_ssl else "http"
    client = VoiceboxApiClient(
        base_url=f"{scheme}://{host}:{port}",
        api_key=api_key,
        session=async_get_clientsession(hass),
        request_timeout=DEFAULT_TIMEOUT,
    )

    try:
        await client.async_status()
    except VoiceboxApiConnectionError as err:
        raise CannotConnect from err
    except VoiceboxApiAuthError as err:
        raise InvalidAuth from err
    except VoiceboxApiResponseError as err:
        raise InvalidResponse from err


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate API authentication failed."""


class InvalidResponse(Exception):
    """Error to indicate we got an unexpected response from the API."""


class InvalidHost(Exception):
    """Error to indicate host input is invalid."""
