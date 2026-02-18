"""InfraGlow — infrastructure metrics on LED strips.

Turns Home Assistant sensor data into real-time LED visualizations on WLED devices.
Supports gauge (fill bar), flow (animated throughput), and alert (override flash) modes.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_WLED_HOST, CONF_WLED_PORT, CONF_VISUALIZATIONS, DEFAULT_PORT
from .coordinator import VisualizationCoordinator
from .wled_client import WLEDClient

_LOGGER = logging.getLogger(__name__)

type InfraGlowConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the InfraGlow component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up InfraGlow from a config entry."""
    host = entry.data[CONF_WLED_HOST]
    port = entry.data.get(CONF_WLED_PORT, DEFAULT_PORT)
    visualizations = entry.data.get(CONF_VISUALIZATIONS, [])

    _LOGGER.info("Setting up InfraGlow for %s:%d", host, port)

    # Create WLED client
    client = WLEDClient(host, port)

    # Create and start coordinator
    coordinator = VisualizationCoordinator(
        hass=hass,
        wled_client=client,
        config={"total_leds": 60},  # Will be overridden by WLED info
    )

    if visualizations:
        await coordinator.async_setup(visualizations)
    else:
        _LOGGER.info(
            "No visualizations configured yet. Use the integration options to add some."
        )

    # Store coordinator for cleanup and options updates
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Listen for options/data updates (when user adds/edits visualizations)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates (visualization changes)."""
    _LOGGER.info("Configuration updated, reloading InfraGlow")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: VisualizationCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)

    if coordinator:
        await coordinator.async_shutdown()

    return True
