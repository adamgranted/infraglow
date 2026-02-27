from __future__ import annotations

from custom_components.infraglow.engine.alert import AlertRenderer


def test_alert_inactive_returns_empty_frame() -> None:
    renderer = AlertRenderer({"flash_color": [255, 0, 0], "flash_speed": 2.0, "flash_style": "pulse"})
    frame = renderer.render(value=0.0, num_leds=10, timestamp=0.0)
    assert frame == []
    assert renderer.is_active is False


def test_alert_solid_style_returns_full_strip() -> None:
    renderer = AlertRenderer({"flash_color": [10, 20, 30], "flash_style": "solid"})
    frame = renderer.render(value=1.0, num_leds=4, timestamp=0.0)
    assert frame == [(10, 20, 30)] * 4
    assert renderer.is_active is True


def test_alert_strobe_style_switches_on_phase() -> None:
    renderer = AlertRenderer({"flash_color": [100, 10, 0], "flash_speed": 1.0, "flash_style": "strobe"})
    on_frame = renderer.render(value=1.0, num_leds=3, timestamp=0.25)
    off_frame = renderer.render(value=1.0, num_leds=3, timestamp=0.75)
    assert on_frame == [(100, 10, 0)] * 3
    assert off_frame == [(0, 0, 0)] * 3


def test_alert_pulse_style_scales_brightness() -> None:
    renderer = AlertRenderer({"flash_color": [200, 100, 0], "flash_speed": 1.0, "flash_style": "pulse"})
    frame = renderer.render(value=1.0, num_leds=2, timestamp=0.0)
    assert len(frame) == 2
    assert frame[0][0] > 0
    assert frame[0][0] < 200


def test_alert_update_config_replaces_flash_values() -> None:
    renderer = AlertRenderer({"flash_color": [255, 0, 0], "flash_speed": 1.0, "flash_style": "solid"})
    renderer.update_config({"flash_color": [0, 0, 255], "flash_speed": 5.0, "flash_style": "strobe"})
    frame = renderer.render(value=1.0, num_leds=1, timestamp=0.0)
    assert frame == [(0, 0, 255)]
