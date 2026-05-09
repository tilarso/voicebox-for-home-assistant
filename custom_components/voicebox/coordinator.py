"""DataUpdateCoordinator for Voicebox."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import VoiceboxApiClient, VoiceboxApiError
from .const import COORDINATOR_UPDATE_INTERVAL, DEFAULT_STATUS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class VoiceboxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Voicebox API status updates for entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: VoiceboxApiClient,
        entry_id: str,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}-{entry_id}",
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self.client = client
        self.entry_id = entry_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Voicebox API."""
        try:
            data = await self.client.async_status()
        except VoiceboxApiError as err:
            raise UpdateFailed(str(err)) from err

        if "status" not in data:
            data = {**data, "status": DEFAULT_STATUS}
        return data
