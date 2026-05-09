"""Voicebox API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncio
import aiohttp


@dataclass(slots=True)
class VoiceboxApiError(Exception):
    """Base class for Voicebox API errors."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class VoiceboxApiConnectionError(VoiceboxApiError):
    """Raised when a network-level API call fails."""


@dataclass(slots=True)
class VoiceboxApiResponseError(VoiceboxApiError):
    """Raised when the Voicebox API returns an unexpected response."""

    status_code: int
    body: Any | None = None


@dataclass(slots=True)
class VoiceboxApiAuthError(VoiceboxApiResponseError):
    """Raised when authentication/authorization fails."""


class VoiceboxApiClient:
    """Client for communicating with a Voicebox API instance."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
        request_timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._request_timeout = request_timeout
        self._session = session
        self._owns_session = session is None

    @property
    def base_url(self) -> str:
        """Return configured base URL."""
        return self._base_url

    async def async_close(self) -> None:
        """Close the owned HTTP session, if created by this client."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    async def async_status(self) -> dict[str, Any]:
        """Fetch current Voicebox status."""
        return await self._request_json("GET", "/api/status")

    async def async_enable(self) -> dict[str, Any]:
        """Enable Voicebox."""
        return await self._request_json("POST", "/api/enable")

    async def async_disable(self) -> dict[str, Any]:
        """Disable Voicebox."""
        return await self._request_json("POST", "/api/disable")

    async def async_set_enabled(self, enabled: bool) -> dict[str, Any]:
        """Enable or disable Voicebox based on boolean input."""
        if enabled:
            return await self.async_enable()
        return await self.async_disable()

    async def async_restart(self) -> dict[str, Any]:
        """Restart Voicebox."""
        return await self._request_json("POST", "/api/restart")

    async def async_synthesize(
        self,
        text: str,
        voice: str | None = None,
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """Request speech synthesis from Voicebox."""
        payload: dict[str, Any] = {"text": text}
        if voice:
            payload["voice"] = voice
        if output_path:
            payload["output_path"] = output_path

        return await self._request_json("POST", "/api/synthesize", json=payload)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._request_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._owns_session = True
        return self._session

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"

        try:
            async with session.request(method, url, headers=self._headers(), json=json) as response:
                body = await self._extract_response_body(response)

                if response.status in {401, 403}:
                    raise VoiceboxApiAuthError(
                        message=f"Voicebox API auth failed for {method} {url} (status={response.status})",
                        status_code=response.status,
                        body=body,
                    )

                if response.status < 200 or response.status >= 300:
                    raise VoiceboxApiResponseError(
                        message=f"Voicebox API error for {method} {url} (status={response.status})",
                        status_code=response.status,
                        body=body,
                    )

                if isinstance(body, dict):
                    return body

                raise VoiceboxApiResponseError(
                    message=f"Voicebox API returned non-object JSON for {method} {url}",
                    status_code=response.status,
                    body=body,
                )
        except VoiceboxApiError:
            raise
        except (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError) as err:
            raise VoiceboxApiConnectionError(
                f"Voicebox API request failed for {method} {url}: {err}"
            ) from err

    async def _extract_response_body(self, response: aiohttp.ClientResponse) -> Any:
        """Try to parse JSON body; return text fallback if parsing fails."""
        if response.content_type == "application/json":
            return await response.json(content_type=None)

        text_body = await response.text()
        if not text_body:
            return {}

        try:
            return await response.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError):
            return text_body
