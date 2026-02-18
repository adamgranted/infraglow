"""Effect renderer — native WLED effect bridge.

Instead of computing per-pixel colors, this renderer outputs WLED effect
parameters (fx, palette, speed, intensity, colors) that let WLED's own
animation engine run while InfraGlow controls the look based on sensor
values.

The sensor's normalized value drives:
  - Color: three-stop gradient mapped into WLED's three color slots
           (primary, secondary, tertiary) centered around the current
           value position so the palette feels cohesive.
  - Speed: higher values = faster animation.
  - Intensity: higher values = more intense effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseRenderer, gradient_color, lerp_color

from ..const import (
    MODE_EFFECT_DEFAULTS,
    WLED_FX_BREATHE,
)


@dataclass
class EffectState:
    """Parameters to push to WLED for one segment."""

    fx: int = 0
    pal: int = 0
    sx: int = 128
    ix: int = 128
    colors: list[list[int]] = field(default_factory=lambda: [[255, 255, 255], [0, 0, 0], [0, 0, 0]])
    mirror: bool = False
    reverse: bool = False


class EffectRenderer(BaseRenderer):
    """Maps sensor values to native WLED effect parameters."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        mode = config.get("mode", "grafana")
        mode_fx = MODE_EFFECT_DEFAULTS.get(mode, {})

        self._fx: int = config.get("wled_fx", mode_fx.get("fx", WLED_FX_BREATHE))
        self._pal: int = config.get("wled_pal", 0)
        self._speed_min: int = config.get("speed_min", mode_fx.get("speed_min", 60))
        self._speed_max: int = config.get("speed_max", mode_fx.get("speed_max", 240))
        self._intensity_min: int = config.get("intensity_min", 80)
        self._intensity_max: int = config.get("intensity_max", 255)
        self._mirror: bool = config.get("mirror", False)
        self._reverse: bool = config.get("reverse", False)

        self._last_state: EffectState | None = None

    def compute_effect_state(self, value: float) -> EffectState:
        """Compute WLED effect parameters from a raw sensor value."""
        t = self.normalize(value)

        primary = gradient_color(t, self._color_low, self._color_high, self._color_mid)

        # Build three color stops centered around the current position to
        # give WLED a cohesive palette around the active value.
        t_lo = max(0.0, t - 0.15)
        t_hi = min(1.0, t + 0.15)
        secondary = gradient_color(t_lo, self._color_low, self._color_high, self._color_mid)
        tertiary = gradient_color(t_hi, self._color_low, self._color_high, self._color_mid)

        sx = int(self._speed_min + (self._speed_max - self._speed_min) * t)
        ix = int(self._intensity_min + (self._intensity_max - self._intensity_min) * t)

        return EffectState(
            fx=self._fx,
            pal=self._pal,
            sx=max(0, min(255, sx)),
            ix=max(0, min(255, ix)),
            colors=[list(primary), list(secondary), list(tertiary)],
            mirror=self._mirror,
            reverse=self._reverse,
        )

    def has_changed(self, new_state: EffectState) -> bool:
        """Return True if the new state differs enough to push an update."""
        old = self._last_state
        if old is None:
            return True
        if old.fx != new_state.fx or old.pal != new_state.pal:
            return True
        if abs(old.sx - new_state.sx) >= 3 or abs(old.ix - new_state.ix) >= 3:
            return True
        for i in range(3):
            for c in range(3):
                if abs(old.colors[i][c] - new_state.colors[i][c]) >= 5:
                    return True
        return False

    def accept_state(self, state: EffectState) -> None:
        """Mark a state as successfully pushed (for change detection)."""
        self._last_state = state

    # BaseRenderer requires this method but for effect mode it is unused.
    # The coordinator calls compute_effect_state directly.
    def render(
        self,
        value: float,
        num_leds: int,
        timestamp: float,
    ) -> list[tuple[int, int, int]]:
        """Not used in effect mode — exists to satisfy the ABC contract."""
        return []

    def update_config(self, config: dict[str, Any]) -> None:
        super().update_config(config)
        mode = config.get("mode", "grafana")
        mode_fx = MODE_EFFECT_DEFAULTS.get(mode, {})
        self._fx = config.get("wled_fx", mode_fx.get("fx", self._fx))
        self._pal = config.get("wled_pal", self._pal)
        self._speed_min = config.get("speed_min", self._speed_min)
        self._speed_max = config.get("speed_max", self._speed_max)
        self._intensity_min = config.get("intensity_min", self._intensity_min)
        self._intensity_max = config.get("intensity_max", self._intensity_max)
        self._mirror = config.get("mirror", self._mirror)
        self._reverse = config.get("reverse", self._reverse)
        self._last_state = None
