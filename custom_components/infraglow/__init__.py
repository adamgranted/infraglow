"""InfraGlow — infrastructure metrics on LED strips.

Turns Home Assistant sensor data into real-time LED visualizations on WLED
devices.  Each WLED device is a single config entry; individual visualizations
are stored as config subentries and exposed as entities on the device page.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_WLED_HOST,
    CONF_WLED_PORT,
    DEFAULT_PORT,
    SUBENTRY_TYPE_VISUALIZATION,
)
from .coordinator import VisualizationCoordinator
from .wled_client import WLEDClient

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry from V1 (visualizations list) to V2 (subentries)."""
    if entry.version < 2:
        _LOGGER.info("Migrating InfraGlow config entry from v%s to v2", entry.version)
        new_data = {
            CONF_WLED_HOST: entry.data[CONF_WLED_HOST],
            CONF_WLED_PORT: entry.data.get(CONF_WLED_PORT, DEFAULT_PORT),
        }
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        _LOGGER.info(
            "Migration complete. Old visualizations removed — "
            "re-add them via the integration page."
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up InfraGlow from a config entry."""
    host = entry.data[CONF_WLED_HOST]
    port = entry.data.get(CONF_WLED_PORT, DEFAULT_PORT)

    hass.data.setdefault(DOMAIN, {})
    _LOGGER.info("Setting up InfraGlow for %s:%d", host, port)

    client = WLEDClient(host, port)

    wled_info: dict[str, Any] = {}
    try:
        wled_info = await client.get_info()
    except Exception:
        _LOGGER.warning("Could not fetch WLED info during setup")

    # Register HA device for the WLED strip
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="WLED",
        model=wled_info.get("arch", "ESP"),
        sw_version=wled_info.get("ver"),
    )

    coordinator = VisualizationCoordinator(
        hass=hass,
        wled_client=client,
        config={"total_leds": wled_info.get("leds", {}).get("count", 60)},
    )

    viz_configs: list[dict[str, Any]] = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VISUALIZATION:
            continue
        cfg = dict(subentry.data)
        cfg["slot_id"] = subentry_id
        viz_configs.append(cfg)

    if viz_configs:
        await coordinator.async_setup(viz_configs)
    else:
        _LOGGER.info(
            "No visualizations configured yet. "
            "Add one from the integration page."
        )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry updates (subentry add/remove/edit)."""
    _LOGGER.info("Configuration updated, reloading InfraGlow")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator: VisualizationCoordinator | None = hass.data[DOMAIN].pop(
        entry.entry_id, None
    )
    if coordinator:
        await coordinator.async_shutdown()

    return unload_ok
