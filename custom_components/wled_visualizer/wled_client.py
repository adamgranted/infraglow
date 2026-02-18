"""WLED JSON API client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import WLED_API_INFO, WLED_API_STATE

_LOGGER = logging.getLogger(__name__)


class WLEDClient:
    """Client for communicating with WLED via HTTP JSON API."""

    def __init__(self, host: str, port: int = 80, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the WLED client."""
        self._host = host
        self._port = port
        self._session = session
        self._base_url = f"http://{host}:{port}"
        self._info: dict[str, Any] | None = None

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self._base_url

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get_info(self) -> dict[str, Any]:
        """Get WLED device info (LED count, segment info, etc.)."""
        session = await self._ensure_session()
        try:
            async with session.get(
                f"{self._base_url}{WLED_API_INFO}",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                resp.raise_for_status()
                self._info = await resp.json()
                return self._info
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to get WLED info from %s: %s", self._base_url, err)
            raise

    async def get_state(self) -> dict[str, Any]:
        """Get current WLED state."""
        session = await self._ensure_session()
        try:
            async with session.get(
                f"{self._base_url}{WLED_API_STATE}",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to get WLED state from %s: %s", self._base_url, err)
            raise

    async def set_segment_colors(
        self,
        segment_id: int,
        colors: list[tuple[int, int, int]],
    ) -> None:
        """Set individual LED colors on a specific segment.

        Args:
            segment_id: WLED segment ID.
            colors: List of (R, G, B) tuples, one per LED in the segment.
        """
        # WLED individual LED control format:
        # {"seg": [{"id": N, "i": [R, G, B, R, G, B, ...]}]}
        flat_colors: list[int] = []
        for r, g, b in colors:
            flat_colors.extend([r, g, b])

        payload = {
            "seg": [{"id": segment_id, "i": flat_colors}],
        }
        await self._send_state(payload)

    async def set_all_leds(
        self,
        colors: list[tuple[int, int, int]],
    ) -> None:
        """Set colors for the entire strip, overriding segment boundaries.

        Temporarily expands segment 0 to cover all LEDs (0 to total count)
        so the alert animation spans the full strip.
        """
        total = self.get_total_leds()
        flat_colors: list[int] = []
        for r, g, b in colors:
            flat_colors.extend([r, g, b])

        payload = {
            "seg": [{"id": 0, "start": 0, "stop": total, "i": flat_colors}],
        }
        await self._send_state(payload)

    async def set_power(self, on: bool) -> None:
        """Turn WLED on or off."""
        await self._send_state({"on": on})

    async def set_brightness(self, brightness: int) -> None:
        """Set master brightness (0-255)."""
        await self._send_state({"bri": max(0, min(255, brightness))})

    async def _send_state(self, payload: dict[str, Any]) -> None:
        """Send a state update to WLED."""
        session = await self._ensure_session()
        try:
            async with session.post(
                f"{self._base_url}{WLED_API_STATE}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                resp.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to send state to %s: %s", self._base_url, err)
            raise

    def get_total_leds(self) -> int:
        """Return total LED count from cached info."""
        if self._info and "leds" in self._info:
            return self._info["leds"].get("count", 0)
        return 0

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
