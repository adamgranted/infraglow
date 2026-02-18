"""Visualization coordinator — the brain of InfraGlow.

Watches Home Assistant entity states, runs the appropriate renderer for each
visualization slot, and pushes updates to WLED via the JSON API.

For metric modes (temperature, load, throughput, generic) the coordinator
sends native WLED effect parameters (fx/pal/speed/intensity/colors) so that
WLED's own animation engine handles movement while InfraGlow controls the
look based on sensor values.

For alert mode, per-pixel override is still used to take over the full strip.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    RENDERER_ALERT,
    RENDERER_EFFECT,
    RENDERER_FLOW,
    RENDERER_GAUGE,
    MODE_RENDERER_MAP,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_EFFECT_UPDATE_INTERVAL,
)
from .engine import (
    AlertRenderer,
    BaseRenderer,
    EffectRenderer,
    FlowRenderer,
    GaugeRenderer,
)
from .wled_client import WLEDClient

_LOGGER = logging.getLogger(__name__)

FRAME_RATE = 15
FRAME_INTERVAL = 1.0 / FRAME_RATE


def _create_renderer(renderer_type: str, config: dict[str, Any]) -> BaseRenderer:
    """Create a renderer instance from type string."""
    if renderer_type == RENDERER_EFFECT:
        return EffectRenderer(config)
    if renderer_type == RENDERER_GAUGE:
        return GaugeRenderer(config)
    if renderer_type == RENDERER_FLOW:
        return FlowRenderer(config)
    if renderer_type == RENDERER_ALERT:
        return AlertRenderer(config)
    raise ValueError(f"Unknown renderer type: {renderer_type}")


def _parse_entity_value(state: State | None) -> float:
    """Extract a numeric value from an HA entity state."""
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return 0.0
    if state.state == STATE_ON:
        return 1.0
    if state.state == STATE_OFF:
        return 0.0
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return 0.0


class VisualizationSlot:
    """A single visualization binding: entity -> renderer -> segment."""

    def __init__(self, slot_id: str, config: dict[str, Any]) -> None:
        self.slot_id = slot_id
        self.config: dict[str, Any] = dict(config)
        self.entity_id: str = config["entity_id"]
        self.segment_id: int = config.get("segment_id", 0)
        self.num_leds: int = config.get("num_leds", 30)
        self.enabled: bool = config.get("enabled", True)

        mode = config.get("mode", "grafana")
        renderer_type = config.get(
            "renderer_type", MODE_RENDERER_MAP.get(mode, RENDERER_EFFECT)
        )

        self.renderer: BaseRenderer = _create_renderer(renderer_type, config)
        self.renderer_type: str = renderer_type
        self.current_value: float = 0.0
        self.last_update: float = 0.0
        self.last_frame: list[tuple[int, int, int]] = []

        if renderer_type == RENDERER_EFFECT:
            self.update_interval: float = config.get(
                "update_interval", DEFAULT_EFFECT_UPDATE_INTERVAL
            )
        else:
            self.update_interval = config.get(
                "update_interval", DEFAULT_UPDATE_INTERVAL
            )

    def normalized_value(self) -> float:
        """Return the current value normalized to 0.0-1.0 by the renderer."""
        return self.renderer.normalize(self.current_value)


class VisualizationCoordinator:
    """Coordinates all visualizations for a single WLED instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        wled_client: WLEDClient,
        config: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.wled = wled_client
        self.slots: dict[str, VisualizationSlot] = {}
        self.alert_slots: dict[str, VisualizationSlot] = {}
        self._unsub_listeners: list[Any] = []
        self._render_task: asyncio.Task | None = None
        self._running = False
        self._total_leds: int = config.get("total_leds", 60)
        self._alert_active: bool = False
        self._alert_frame: list[tuple[int, int, int]] = []

    async def async_setup(self, visualizations: list[dict[str, Any]]) -> None:
        """Set up all visualization slots and start the render loop."""
        try:
            info = await self.wled.get_info()
            self._total_leds = info.get("leds", {}).get("count", self._total_leds)
            _LOGGER.info(
                "Connected to WLED at %s — %d LEDs",
                self.wled.base_url,
                self._total_leds,
            )
        except Exception:
            _LOGGER.warning(
                "Could not get WLED info, using configured LED count: %d",
                self._total_leds,
            )

        try:
            await self.wled.prepare_for_control()
        except Exception:
            _LOGGER.warning("Could not prepare WLED for control")

        for i, viz_config in enumerate(visualizations):
            slot_id = viz_config.get("slot_id", f"viz_{i}")
            slot = VisualizationSlot(slot_id, viz_config)

            if slot.renderer_type == RENDERER_ALERT:
                self.alert_slots[slot_id] = slot
            else:
                self.slots[slot_id] = slot

            _LOGGER.info(
                "Visualization '%s': entity=%s, segment=%d, renderer=%s",
                slot_id,
                slot.entity_id,
                slot.segment_id,
                slot.renderer_type,
            )

        all_entity_ids = [s.entity_id for s in self._all_slots()]
        if all_entity_ids:
            unsub = async_track_state_change_event(
                self.hass, all_entity_ids, self._handle_state_change,
            )
            self._unsub_listeners.append(unsub)

        for slot in self._all_slots():
            state = self.hass.states.get(slot.entity_id)
            slot.current_value = _parse_entity_value(state)

        self._running = True
        self._render_task = self.hass.async_create_task(self._render_loop())

    def get_slot(self, slot_id: str) -> VisualizationSlot | None:
        """Get a slot by its ID (subentry ID)."""
        return self.slots.get(slot_id) or self.alert_slots.get(slot_id)

    def update_slot_param(self, slot_id: str, key: str, value: Any) -> None:
        """Update a single parameter on a slot's renderer in real-time."""
        slot = self.get_slot(slot_id)
        if slot is None:
            return

        slot.config[key] = value

        if key == "enabled":
            slot.enabled = bool(value)
            return

        slot.renderer.update_config(slot.config)
        _LOGGER.debug("Live-updated '%s'.%s = %s", slot_id, key, value)

    def _all_slots(self) -> list[VisualizationSlot]:
        return list(self.slots.values()) + list(self.alert_slots.values())

    @callback
    def _handle_state_change(self, event) -> None:
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        value = _parse_entity_value(new_state)
        for slot in self._all_slots():
            if slot.entity_id == entity_id:
                slot.current_value = value

    async def _render_loop(self) -> None:
        """Main render loop."""
        _LOGGER.debug("Render loop started")

        while self._running:
            try:
                now = time.monotonic()
                timestamp = time.time()

                alert_active = False
                alert_frame: list[tuple[int, int, int]] = []

                for slot in self.alert_slots.values():
                    if not slot.enabled:
                        continue
                    frame = slot.renderer.render(
                        slot.current_value, self._total_leds, timestamp,
                    )
                    if frame:
                        alert_active = True
                        alert_frame = frame
                        break

                if alert_active:
                    if alert_frame:
                        try:
                            await self.wled.set_all_leds(alert_frame)
                        except Exception as err:
                            _LOGGER.warning("Failed to push alert frame: %s", err)
                    self._alert_active = True
                else:
                    if self._alert_active:
                        _LOGGER.info("Alert cleared, resuming normal visualizations")
                        self._alert_active = False
                        for slot in self.slots.values():
                            if slot.renderer_type == RENDERER_EFFECT:
                                slot.renderer._last_state = None

                    for slot in self.slots.values():
                        if not slot.enabled:
                            continue

                        if slot.renderer_type == RENDERER_GAUGE:
                            if now - slot.last_update < slot.update_interval:
                                continue

                        if slot.renderer_type == RENDERER_EFFECT:
                            if now - slot.last_update < slot.update_interval:
                                continue
                            await self._push_effect_slot(slot)
                        else:
                            await self._push_pixel_slot(slot, timestamp)

                        slot.last_update = now

                elapsed = time.monotonic() - now
                sleep_time = max(0.01, FRAME_INTERVAL - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception:
                _LOGGER.exception("Error in render loop")
                await asyncio.sleep(1.0)

        _LOGGER.debug("Render loop stopped")

    async def _push_effect_slot(self, slot: VisualizationSlot) -> None:
        """Compute and push native WLED effect parameters for a slot."""
        renderer: EffectRenderer = slot.renderer  # type: ignore[assignment]
        state = renderer.compute_effect_state(slot.current_value)

        if not renderer.has_changed(state):
            return

        try:
            await self.wled.set_segment_effect(
                slot.segment_id,
                fx=state.fx,
                pal=state.pal,
                sx=state.sx,
                ix=state.ix,
                colors=state.colors,
                mirror=state.mirror,
                reverse=state.reverse,
            )
            renderer.accept_state(state)
        except Exception as err:
            _LOGGER.warning(
                "Failed to push effect for '%s': %s", slot.slot_id, err,
            )

    async def _push_pixel_slot(
        self, slot: VisualizationSlot, timestamp: float,
    ) -> None:
        """Render and push per-pixel colors for a slot (gauge/flow)."""
        frame = slot.renderer.render(
            slot.current_value, slot.num_leds, timestamp,
        )
        slot.last_frame = frame
        try:
            await self.wled.set_segment_colors(slot.segment_id, frame)
        except Exception as err:
            _LOGGER.warning(
                "Failed to push frame for '%s': %s", slot.slot_id, err,
            )

    async def async_shutdown(self) -> None:
        _LOGGER.info("Shutting down InfraGlow coordinator")
        self._running = False

        if self._render_task:
            self._render_task.cancel()
            try:
                await self._render_task
            except asyncio.CancelledError:
                pass

        for unsub in self._unsub_listeners:
            unsub()

        await self.wled.close()
