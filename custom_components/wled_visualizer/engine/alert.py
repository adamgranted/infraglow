"""Alert renderer — binary override flasher.

When triggered, takes over the entire LED strip with a pulsing flash
animation. Ignores segments and floor/ceiling — it's either on or off.
"""

from __future__ import annotations

import math
from typing import Any

from .base import BaseRenderer, lerp_color


class AlertRenderer(BaseRenderer):
    """Renders an alert flash that overrides the entire strip."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize alert renderer."""
        super().__init__(config)
        self._flash_color: tuple[int, int, int] = tuple(
            config.get("flash_color", [255, 0, 0])
        )
        self._flash_speed: float = config.get("flash_speed", 2.0)  # Hz
        self._style: str = config.get("flash_style", "pulse")  # pulse | strobe | solid
        self._last_active: bool = False

    @property
    def is_active(self) -> bool:
        """Check if alert should be active based on last value."""
        return self._last_active

    def render(
        self,
        value: float,
        num_leds: int,
        timestamp: float,
    ) -> list[tuple[int, int, int]]:
        """Render an alert flash frame.

        Args:
            value: Treated as boolean — anything > 0 means alert is active.
                   For binary_sensor entities, HA converts on/off to 1/0.
            num_leds: Total LED count for the ENTIRE strip (not a segment).
            timestamp: Current time in seconds.

        Returns:
            Full strip of colors when active, empty list when inactive.
        """
        # Store active state for coordinator to check
        self._last_active = float(value) > 0

        if not self._last_active:
            return []  # Empty = no override, let other visualizations run

        if self._style == "strobe":
            # Hard on/off strobe
            phase = (timestamp * self._flash_speed) % 1.0
            if phase < 0.5:
                return [self._flash_color] * num_leds
            else:
                return [(0, 0, 0)] * num_leds

        elif self._style == "solid":
            # Solid color, no animation
            return [self._flash_color] * num_leds

        else:
            # Smooth pulse (default)
            phase = math.sin(timestamp * self._flash_speed * math.pi * 2.0)
            # Map sine (-1 to 1) to brightness (0.15 to 1.0) — never fully off
            brightness = 0.15 + 0.85 * ((phase + 1.0) / 2.0)
            color = (
                int(self._flash_color[0] * brightness),
                int(self._flash_color[1] * brightness),
                int(self._flash_color[2] * brightness),
            )
            return [color] * num_leds

    def update_config(self, config: dict[str, Any]) -> None:
        """Update configuration."""
        super().update_config(config)
        if "flash_color" in config:
            self._flash_color = tuple(config["flash_color"])
        self._flash_speed = config.get("flash_speed", self._flash_speed)
        self._style = config.get("flash_style", self._style)
