"""Base visualization renderer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


def lerp_color(
    color_a: tuple[int, int, int],
    color_b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """Linearly interpolate between two RGB colors.

    Args:
        color_a: Start color (R, G, B).
        color_b: End color (R, G, B).
        t: Interpolation factor, 0.0 = color_a, 1.0 = color_b.

    Returns:
        Interpolated (R, G, B) tuple.
    """
    t = max(0.0, min(1.0, t))
    return (
        int(color_a[0] + (color_b[0] - color_a[0]) * t),
        int(color_a[1] + (color_b[1] - color_a[1]) * t),
        int(color_a[2] + (color_b[2] - color_a[2]) * t),
    )


def gradient_color(
    t: float,
    color_low: tuple[int, int, int],
    color_high: tuple[int, int, int],
    color_mid: tuple[int, int, int] | None = None,
) -> tuple[int, int, int]:
    """Get a color from a gradient at position t (0.0-1.0).

    If color_mid is provided, uses a three-stop gradient:
    0.0 = color_low, 0.5 = color_mid, 1.0 = color_high.
    """
    if color_mid is None:
        return lerp_color(color_low, color_high, t)

    if t <= 0.5:
        return lerp_color(color_low, color_mid, t * 2.0)
    else:
        return lerp_color(color_mid, color_high, (t - 0.5) * 2.0)


class BaseRenderer(ABC):
    """Abstract base class for visualization renderers."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the renderer with its configuration."""
        self._config = config
        self._floor: float = config.get("floor", 0.0)
        self._ceiling: float = config.get("ceiling", 100.0)
        self._color_low: tuple[int, int, int] = tuple(config.get("color_low", [0, 255, 0]))
        self._color_high: tuple[int, int, int] = tuple(config.get("color_high", [255, 0, 0]))
        self._color_mid: tuple[int, int, int] | None = (
            tuple(config["color_mid"]) if "color_mid" in config else None
        )

    def normalize(self, raw_value: float) -> float:
        """Normalize a raw value to 0.0-1.0 based on floor/ceiling.

        Values below floor clamp to 0.0, above ceiling clamp to 1.0.
        """
        if self._ceiling == self._floor:
            return 0.0
        normalized = (raw_value - self._floor) / (self._ceiling - self._floor)
        return max(0.0, min(1.0, normalized))

    @abstractmethod
    def render(
        self,
        value: float,
        num_leds: int,
        timestamp: float,
    ) -> list[tuple[int, int, int]]:
        """Render a frame of LED colors.

        Args:
            value: The current raw sensor value.
            num_leds: Number of LEDs in the target segment.
            timestamp: Current time in seconds (for animations).

        Returns:
            List of (R, G, B) tuples, one per LED.
        """

    def update_config(self, config: dict[str, Any]) -> None:
        """Update renderer configuration dynamically."""
        self._config = config
        self._floor = config.get("floor", self._floor)
        self._ceiling = config.get("ceiling", self._ceiling)
        if "color_low" in config:
            self._color_low = tuple(config["color_low"])
        if "color_high" in config:
            self._color_high = tuple(config["color_high"])
        if "color_mid" in config:
            self._color_mid = tuple(config["color_mid"])
