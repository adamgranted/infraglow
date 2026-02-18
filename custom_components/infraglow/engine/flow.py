"""Flow renderer — animated speed-based visualization.

Creates a flowing/scrolling animation where the speed of movement is
proportional to the sensor value. Ideal for network throughput where
higher bandwidth = faster animation.

The animation consists of colored "pulses" that travel along the strip.
Color intensity reflects the current value level.
"""

from __future__ import annotations

import math
from typing import Any

from .base import BaseRenderer, gradient_color, lerp_color


class FlowRenderer(BaseRenderer):
    """Renders a flowing animation whose speed maps to sensor value."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize flow renderer."""
        super().__init__(config)
        # How many LED positions per second at max value
        self._max_speed: float = config.get("max_speed", 30.0)
        # Minimum speed so there's always some movement when value > 0
        self._min_speed: float = config.get("min_speed", 1.0)
        # Width of each pulse in LEDs
        self._pulse_width: float = config.get("pulse_width", 5.0)
        # Gap between pulses in LEDs
        self._pulse_gap: float = config.get("pulse_gap", 8.0)
        # Flow direction: 1 = left-to-right, -1 = right-to-left
        self._direction: int = 1 if config.get("flow_direction", "forward") == "forward" else -1
        # Background color (dim version of the base color)
        self._bg_brightness: float = config.get("bg_brightness", 0.05)

    def render(
        self,
        value: float,
        num_leds: int,
        timestamp: float,
    ) -> list[tuple[int, int, int]]:
        """Render a flow animation frame.

        The animation creates repeating pulses that scroll along the strip.
        Speed is proportional to the normalized value. Color shifts from
        color_low to color_high based on value intensity.
        """
        normalized = self.normalize(value)

        if normalized <= 0.0:
            # At or below floor — show dim background
            bg = self._make_background_color(0.0, num_leds)
            return bg

        # Calculate current speed (LED positions per second)
        speed = self._min_speed + (self._max_speed - self._min_speed) * normalized

        # Current color based on value level
        current_color = gradient_color(
            normalized, self._color_low, self._color_high, self._color_mid
        )

        # Calculate animation offset based on time and speed
        offset = (timestamp * speed * self._direction) % (self._pulse_width + self._pulse_gap)

        # Render each LED
        pattern_length = self._pulse_width + self._pulse_gap
        result: list[tuple[int, int, int]] = []

        for i in range(num_leds):
            # Position in the repeating pattern
            pos = (i + offset) % pattern_length

            if pos < self._pulse_width:
                # Inside a pulse — use a smooth falloff for the pulse shape
                pulse_center = self._pulse_width / 2.0
                distance_from_center = abs(pos - pulse_center) / pulse_center
                # Smooth bell curve falloff
                intensity = math.cos(distance_from_center * math.pi / 2.0) ** 2
                # Scale intensity by the normalized value
                intensity *= (0.3 + 0.7 * normalized)

                color = lerp_color((0, 0, 0), current_color, intensity)
                result.append(color)
            else:
                # In the gap — dim background
                bg_color = tuple(
                    int(c * self._bg_brightness * normalized)
                    for c in current_color
                )
                result.append(bg_color)

        return result

    def _make_background_color(
        self,
        normalized: float,
        num_leds: int,
    ) -> list[tuple[int, int, int]]:
        """Generate a dim background."""
        base = gradient_color(
            max(normalized, 0.01),
            self._color_low,
            self._color_high,
            self._color_mid,
        )
        bg = (
            int(base[0] * self._bg_brightness),
            int(base[1] * self._bg_brightness),
            int(base[2] * self._bg_brightness),
        )
        return [bg] * num_leds

    def update_config(self, config: dict[str, Any]) -> None:
        """Update configuration."""
        super().update_config(config)
        self._max_speed = config.get("max_speed", self._max_speed)
        self._min_speed = config.get("min_speed", self._min_speed)
        self._pulse_width = config.get("pulse_width", self._pulse_width)
        self._pulse_gap = config.get("pulse_gap", self._pulse_gap)
