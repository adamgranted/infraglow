from __future__ import annotations

from dataclasses import replace
from typing import Any

from custom_components.infraglow.engine.effect import EffectRenderer


def test_compute_effect_state_without_black(effect_config: dict[str, Any]) -> None:
    renderer = EffectRenderer(effect_config)
    state = renderer.compute_effect_state(50)

    assert state.fx == effect_config["wled_fx"]
    assert state.pal == effect_config["wled_pal"]
    assert state.sx == 55
    assert state.ix == 70
    assert len(state.colors) == 3
    assert state.colors[0] == [127, 127, 0]
    assert state.colors[1] != [0, 0, 0]
    assert state.colors[2] != [0, 0, 0]


def test_compute_effect_state_with_black_insertion(effect_config: dict[str, Any]) -> None:
    config = dict(effect_config)
    config["include_black"] = True
    renderer = EffectRenderer(config)
    state = renderer.compute_effect_state(50)

    assert state.colors[1] == [0, 0, 0]


def test_has_changed_respects_thresholds(effect_config: dict[str, Any]) -> None:
    renderer = EffectRenderer(effect_config)
    baseline = renderer.compute_effect_state(40)

    assert renderer.has_changed(baseline) is True
    renderer.accept_state(baseline)
    assert renderer.has_changed(baseline) is False

    small_delta = replace(baseline, sx=baseline.sx + 2)
    assert renderer.has_changed(small_delta) is False

    speed_threshold_delta = replace(baseline, sx=baseline.sx + 3)
    assert renderer.has_changed(speed_threshold_delta) is True

    color_threshold_delta = replace(
        baseline, colors=[[baseline.colors[0][0] + 5, baseline.colors[0][1], baseline.colors[0][2]], baseline.colors[1], baseline.colors[2]]
    )
    assert renderer.has_changed(color_threshold_delta) is True


def test_update_config_resets_change_tracking(effect_config: dict[str, Any]) -> None:
    renderer = EffectRenderer(effect_config)
    state = renderer.compute_effect_state(25)
    renderer.accept_state(state)
    renderer.update_config({"speed_min": 0})
    assert renderer.has_changed(state) is True
