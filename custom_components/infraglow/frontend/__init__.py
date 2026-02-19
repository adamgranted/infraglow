"""Auto-register the InfraGlow Lovelace card."""

from __future__ import annotations

import logging
import pathlib

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from ..const import URL_BASE, INFRAGLOW_CARDS

_LOGGER = logging.getLogger(__name__)


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve card assets and register as a Lovelace resource."""
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, str(pathlib.Path(__file__).parent), False)]
        )
    except RuntimeError:
        _LOGGER.debug("InfraGlow static path already registered")

    if hass.data["lovelace"].mode != "storage":
        return

    resources = hass.data["lovelace"].resources

    async def _register_when_ready(now):
        if not resources.loaded:
            _LOGGER.debug("Lovelace resources not loaded yet, retrying in 5s")
            async_call_later(hass, 5, _register_when_ready)
            return

        for card in INFRAGLOW_CARDS:
            url = f"{URL_BASE}/{card['filename']}"
            existing = [
                r
                for r in resources.async_items()
                if r["url"].split("?")[0] == url
            ]
            version_url = f"{url}?v={card['version']}"

            if existing:
                if not existing[0]["url"].endswith(f"v={card['version']}"):
                    _LOGGER.debug(
                        "Updating %s to version %s", card["name"], card["version"]
                    )
                    await resources.async_update_item(
                        existing[0]["id"],
                        {"res_type": "module", "url": version_url},
                    )
                else:
                    _LOGGER.debug(
                        "%s already registered at version %s",
                        card["name"],
                        card["version"],
                    )
            else:
                _LOGGER.debug(
                    "Registering %s version %s", card["name"], card["version"]
                )
                await resources.async_create_item(
                    {"res_type": "module", "url": version_url}
                )

    await _register_when_ready(0)
