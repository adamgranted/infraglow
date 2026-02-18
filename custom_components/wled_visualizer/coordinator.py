"""Visualization coordinator — the brain of InfraGlow.

Watches Home Assistant entity states, runs the appropriate renderer for each
visualization slot, and pushes LED frames to WLED via the JSON API.

Handles the alert override system: when any alert renderer reports active,
the coordinator stops pushing segment-based frames and instead pushes the
alert animation to the entire strip.
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
    RENDERER_FLOW,
    RENDERER_GAUGE,
    MODE_RENDERER_MAP,
    DEFAULT_UPDATE_INTERVAL,
)
from .engine import AlertRenderer, FlowRenderer, GaugeRenderer, BaseRenderer
from .wled_client import WLEDClient

_LOGGER = logging.getLogger(__name__)

# Target frame rate for animations (Hz)
FRAME_RATE = 15
FRAME_INTERVAL = 1.0 / FRAME_RATE


def _create_renderer(renderer_type: str, config: dict[str, Any]) -> BaseRenderer:
    """Create a renderer instance from type string."""
    if renderer_type == RENDERER_GAUGE:
        return GaugeRenderer(config)
    elif renderer_type == RENDERER_FLOW:
        return FlowRenderer(config)
    elif renderer_type == RENDERER_ALERT:
        return AlertRenderer(config)
    else:
        raise ValueError(f"Unknown renderer type: {renderer_type}")


def _parse_entity_value(state: State | None) -> float:
    """Extract a numeric value from an HA entity state.

    For binary_sensors: on = 1.0, off = 0.0.
    For numeric sensors: parse the state string as float.
    """
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return 0.0

    # Binary sensor handling
    if state.state == STATE_ON:
        return 1.0
    if state.state == STATE_OFF:
        return 0.0

    try:
        return float(state.state)
    except (ValueError, TypeError):
        return 0.0


class VisualizationSlot:
    """A single visualization binding: entity → renderer → segment."""

    def __init__(
        self,
        viz_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize a visualization slot."""
        self.viz_id = viz_id
        self.entity_id: str = config["entity_id"]
        self.segment_id: int = config.get("segment_id", 0)
        self.num_leds: int = config.get("num_leds", 30)
        self.update_interval: float = config.get("update_interval", DEFAULT_UPDATE_INTERVAL)

        # Determine renderer type from mode or explicit setting
        mode = config.get("mode", "grafana")
        renderer_type = config.get("renderer_type", MODE_RENDERER_MAP.get(mode, RENDERER_GAUGE))

        self.renderer: BaseRenderer = _create_renderer(renderer_type, config)
        self.renderer_type: str = renderer_type
        self.current_value: float = 0.0
        self.last_update: float = 0.0
        self.last_frame: list[tuple[int, int, int]] = []


class VisualizationCoordinator:
    """Coordinates all visualizations for a single WLED instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        wled_client: WLEDClient,
        config: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.wled = wled_client
        self._slots: dict[str, VisualizationSlot] = {}
        self._alert_slots: dict[str, VisualizationSlot] = {}
        self._unsub_listeners: list[Any] = []
        self._render_task: asyncio.Task | None = None
        self._running = False
        self._total_leds: int = config.get("total_leds", 60)
        self._alert_active: bool = False
        self._alert_frame: list[tuple[int, int, int]] = []

    async def async_setup(self, visualizations: list[dict[str, Any]]) -> None:
        """Set up all visualization slots and start the render loop."""
        # Get WLED info to know total LED count
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

        # Ensure WLED is on with instant transitions for per-pixel control
        try:
            await self.wled.prepare_for_control()
        except Exception:
            _LOGGER.warning("Could not prepare WLED for control")

        # Create visualization slots
        for i, viz_config in enumerate(visualizations):
            viz_id = viz_config.get("id", f"viz_{i}")
            slot = VisualizationSlot(viz_id, viz_config)

            if slot.renderer_type == RENDERER_ALERT:
                self._alert_slots[viz_id] = slot
            else:
                self._slots[viz_id] = slot

            _LOGGER.info(
                "Visualization '%s': entity=%s, segment=%d, renderer=%s",
                viz_id,
                slot.entity_id,
                slot.segment_id,
                slot.renderer_type,
            )

        # Set up state listeners for all watched entities
        all_entity_ids = [s.entity_id for s in self._all_slots()]
        if all_entity_ids:
            unsub = async_track_state_change_event(
                self.hass,
                all_entity_ids,
                self._handle_state_change,
            )
            self._unsub_listeners.append(unsub)

        # Initialize current values from HA state
        for slot in self._all_slots():
            state = self.hass.states.get(slot.entity_id)
            slot.current_value = _parse_entity_value(state)

        # Start render loop
        self._running = True
        self._render_task = self.hass.async_create_task(self._render_loop())

    def _all_slots(self) -> list[VisualizationSlot]:
        """Return all slots (regular + alert)."""
        return list(self._slots.values()) + list(self._alert_slots.values())

    @callback
    def _handle_state_change(self, event) -> None:
        """Handle HA entity state changes."""
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        value = _parse_entity_value(new_state)

        for slot in self._all_slots():
            if slot.entity_id == entity_id:
                slot.current_value = value

    async def _render_loop(self) -> None:
        """Main render loop — generates and pushes frames to WLED."""
        _LOGGER.debug("Render loop started")

        while self._running:
            try:
                now = time.monotonic()
                timestamp = time.time()

                # Check alert state first
                alert_active = False
                alert_frame: list[tuple[int, int, int]] = []

                for slot in self._alert_slots.values():
                    frame = slot.renderer.render(
                        slot.current_value,
                        self._total_leds,
                        timestamp,
                    )
                    if frame:  # Non-empty = alert is active
                        alert_active = True
                        alert_frame = frame
                        break  # First active alert wins

                if alert_active:
                    # Override everything — push alert to entire strip
                    if alert_frame:
                        try:
                            await self.wled.set_all_leds(alert_frame)
                        except Exception as err:
                            _LOGGER.warning("Failed to push alert frame: %s", err)
                    self._alert_active = True
                else:
                    # Normal mode — render each visualization to its segment
                    if self._alert_active:
                        _LOGGER.info("Alert cleared, resuming normal visualizations")
                        self._alert_active = False

                    for slot in self._slots.values():
                        # Respect per-slot update intervals for non-animated renderers
                        if slot.renderer_type == RENDERER_GAUGE:
                            if now - slot.last_update < slot.update_interval:
                                # Use cached frame
                                if slot.last_frame:
                                    continue

                        frame = slot.renderer.render(
                            slot.current_value,
                            slot.num_leds,
                            timestamp,
                        )
                        slot.last_frame = frame
                        slot.last_update = now

                        try:
                            await self.wled.set_segment_colors(slot.segment_id, frame)
                        except Exception as err:
                            _LOGGER.warning(
                                "Failed to push frame for '%s': %s",
                                slot.viz_id,
                                err,
                            )

                # Sleep until next frame
                elapsed = time.monotonic() - now
                sleep_time = max(0.01, FRAME_INTERVAL - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception:
                _LOGGER.exception("Error in render loop")
                await asyncio.sleep(1.0)

        _LOGGER.debug("Render loop stopped")

    async def async_update_visualization(
        self,
        viz_id: str,
        config: dict[str, Any],
    ) -> None:
        """Update a visualization's configuration at runtime."""
        slot = self._slots.get(viz_id) or self._alert_slots.get(viz_id)
        if slot:
            slot.renderer.update_config(config)
            _LOGGER.info("Updated visualization '%s'", viz_id)

    async def async_shutdown(self) -> None:
        """Stop the coordinator and clean up."""
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
