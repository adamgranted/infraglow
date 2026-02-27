from __future__ import annotations

from custom_components.infraglow.engine.base import BaseRenderer, gradient_color, lerp_color


class DummyRenderer(BaseRenderer):
    def render(self, value: float, num_leds: int, timestamp: float) -> list[tuple[int, int, int]]:
        return []


def test_lerp_color_clamps_bounds() -> None:
    assert lerp_color((0, 0, 0), (255, 255, 255), -1.0) == (0, 0, 0)
    assert lerp_color((0, 0, 0), (255, 255, 255), 2.0) == (255, 255, 255)


def test_lerp_color_midpoint() -> None:
    assert lerp_color((0, 255, 0), (255, 0, 0), 0.5) == (127, 127, 0)


def test_gradient_color_two_stop() -> None:
    assert gradient_color(0.0, (0, 255, 0), (255, 0, 0)) == (0, 255, 0)
    assert gradient_color(1.0, (0, 255, 0), (255, 0, 0)) == (255, 0, 0)


def test_gradient_color_three_stop() -> None:
    low = (0, 255, 0)
    mid = (255, 255, 0)
    high = (255, 0, 0)
    assert gradient_color(0.25, low, high, mid) == (127, 255, 0)
    assert gradient_color(0.75, low, high, mid) == (255, 127, 0)


def test_normalize_clamps_to_range() -> None:
    renderer = DummyRenderer({"floor": 10, "ceiling": 30})
    assert renderer.normalize(10) == 0.0
    assert renderer.normalize(20) == 0.5
    assert renderer.normalize(30) == 1.0
    assert renderer.normalize(100) == 1.0
    assert renderer.normalize(-100) == 0.0


def test_normalize_returns_zero_when_floor_equals_ceiling() -> None:
    renderer = DummyRenderer({"floor": 5, "ceiling": 5})
    assert renderer.normalize(5) == 0.0


def test_update_config_updates_render_bounds_and_colors() -> None:
    renderer = DummyRenderer(
        {"floor": 0, "ceiling": 100, "color_low": [0, 255, 0], "color_high": [255, 0, 0]}
    )
    renderer.update_config(
        {
            "floor": 20,
            "ceiling": 120,
            "color_low": [0, 0, 255],
            "color_high": [255, 255, 255],
            "color_mid": [10, 20, 30],
        }
    )
    assert renderer.normalize(20) == 0.0
    assert renderer.normalize(70) == 0.5
