"""Gauge renderer — fill bar visualization.

Maps a normalized value (0.0-1.0) to a proportional fill of the LED strip.
The fill position determines how many LEDs are lit, and each lit LED's color
is determined by its position in the gradient (color_low → color_mid → color_high).
"""

from __future__ import annotations

from typing import Any

from .base import BaseRenderer, gradient_color

from ..const import (
    FILL_CENTER_OUT,
    FILL_EDGES_IN,
    FILL_LEFT_TO_RIGHT,
    FILL_RIGHT_TO_LEFT,
    DEFAULT_FILL_DIRECTION,
)


OFF = (0, 0, 0)


class GaugeRenderer(BaseRenderer):
    """Renders a gauge/fill bar visualization."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize gauge renderer."""
        super().__init__(config)
        self._fill_direction: str = config.get("fill_direction", DEFAULT_FILL_DIRECTION)

    def render(
        self,
        value: float,
        num_leds: int,
        timestamp: float,
    ) -> list[tuple[int, int, int]]:
        """Render a fill bar frame.

        The fill level corresponds to the normalized value. Each lit LED gets
        a color from the gradient based on its position in the filled region.
        Unlit LEDs are off (0, 0, 0).
        """
        normalized = self.normalize(value)
        fill_count = int(round(normalized * num_leds))

        # Generate colors for the filled portion
        filled_colors: list[tuple[int, int, int]] = []
        for i in range(fill_count):
            # Color position is based on where this LED sits in the total strip
            # so a half-filled strip at 50% still shows green→yellow, not green→red
            t = i / max(num_leds - 1, 1)
            filled_colors.append(gradient_color(t, self._color_low, self._color_high, self._color_mid))

        unfilled = [OFF] * (num_leds - fill_count)

        return self._apply_direction(filled_colors, unfilled, num_leds)

    def _apply_direction(
        self,
        filled: list[tuple[int, int, int]],
        unfilled: list[tuple[int, int, int]],
        num_leds: int,
    ) -> list[tuple[int, int, int]]:
        """Apply fill direction to the LED array."""
        if self._fill_direction == FILL_LEFT_TO_RIGHT:
            return filled + unfilled

        elif self._fill_direction == FILL_RIGHT_TO_LEFT:
            return unfilled + list(reversed(filled))

        elif self._fill_direction == FILL_CENTER_OUT:
            # Fill from center outward
            result = [OFF] * num_leds
            center = num_leds // 2

            for i in range(len(filled)):
                half_i = i // 2
                if i % 2 == 0:
                    # Right side
                    idx = center + half_i
                else:
                    # Left side
                    idx = center - 1 - half_i
                if 0 <= idx < num_leds:
                    t = i / max(len(filled) - 1, 1)
                    result[idx] = gradient_color(
                        t, self._color_low, self._color_high, self._color_mid
                    )
            return result

        elif self._fill_direction == FILL_EDGES_IN:
            # Fill from both edges toward center
            result = [OFF] * num_leds
            half_fill = len(filled) // 2
            remainder = len(filled) % 2

            for i in range(half_fill + remainder):
                t = i / max(half_fill, 1)
                color = gradient_color(t, self._color_low, self._color_high, self._color_mid)
                # Left edge
                if i < num_leds:
                    result[i] = color
                # Right edge
                right_idx = num_leds - 1 - i
                if right_idx >= 0:
                    result[right_idx] = color
            return result

        # Fallback
        return filled + unfilled

    def update_config(self, config: dict[str, Any]) -> None:
        """Update configuration."""
        super().update_config(config)
        self._fill_direction = config.get("fill_direction", self._fill_direction)
