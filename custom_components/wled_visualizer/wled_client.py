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
        # WLED's "i" array requires non-integer elements (hex strings or
        # sub-arrays) to be recognized as colors. Flat integers are parsed
        # as LED indices. Hex strings are the most bandwidth-efficient format.
        hex_colors = [f"{r:02X}{g:02X}{b:02X}" for r, g, b in colors]
        payload = {
            "seg": [{"id": segment_id, "i": hex_colors}],
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
        hex_colors = [f"{r:02X}{g:02X}{b:02X}" for r, g, b in colors]
        payload = {
            "seg": [{"id": 0, "start": 0, "stop": total, "i": hex_colors}],
        }
        await self._send_state(payload)

    async def set_segment_effect(
        self,
        segment_id: int,
        *,
        fx: int | None = None,
        pal: int | None = None,
        sx: int | None = None,
        ix: int | None = None,
        colors: list[list[int]] | None = None,
        mirror: bool | None = None,
        reverse: bool | None = None,
    ) -> None:
        """Set native WLED effect parameters on a segment.

        This lets WLED run its own animation engine while InfraGlow
        controls which effect, palette, speed, intensity, and colors are
        active. Much lower bandwidth than per-pixel control and enables
        real movement.

        Args:
            segment_id: WLED segment ID.
            fx: Effect ID (0 = Solid, see WLED effect list).
            pal: Palette ID.
            sx: Effect speed (0-255).
            ix: Effect intensity (0-255).
            colors: Up to 3 colors as [[R,G,B], [R,G,B], [R,G,B]].
            mirror: Mirror the segment animation.
            reverse: Reverse the segment animation direction.
        """
        seg: dict[str, Any] = {"id": segment_id}
        if fx is not None:
            seg["fx"] = fx
        if pal is not None:
            seg["pal"] = pal
        if sx is not None:
            seg["sx"] = max(0, min(255, sx))
        if ix is not None:
            seg["ix"] = max(0, min(255, ix))
        if colors is not None:
            seg["col"] = colors
        if mirror is not None:
            seg["mi"] = mirror
        if reverse is not None:
            seg["rev"] = reverse
        # Unfreeze the segment so native effects can run
        seg["frz"] = False
        await self._send_state({"seg": [seg]})

    async def prepare_for_control(self) -> None:
        """Turn WLED on and disable transitions for per-pixel control.

        WLED's default 700ms transition causes sluggish updates when pushing
        individual LED colors at high frame rates. Setting transition to 0
        makes color changes instant.
        """
        await self._send_state({"on": True, "transition": 0})

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
