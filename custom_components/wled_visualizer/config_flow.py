"""Config flow for InfraGlow."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_WLED_HOST,
    CONF_WLED_PORT,
    CONF_VISUALIZATIONS,
    DEFAULT_PORT,
    MODE_SYSTEM_LOAD,
    MODE_TEMPERATURE,
    MODE_THROUGHPUT,
    MODE_ALERT,
    MODE_GRAFANA,
    RENDERER_GAUGE,
    RENDERER_FLOW,
    RENDERER_ALERT,
    MODE_RENDERER_MAP,
    MODE_DEFAULTS,
    FILL_LEFT_TO_RIGHT,
    FILL_RIGHT_TO_LEFT,
    FILL_CENTER_OUT,
    FILL_EDGES_IN,
    DEFAULT_COLOR_LOW,
    DEFAULT_COLOR_HIGH,
    DEFAULT_FLASH_COLOR,
    DEFAULT_UPDATE_INTERVAL,
)
from .wled_client import WLEDClient

_LOGGER = logging.getLogger(__name__)

MODE_OPTIONS = {
    MODE_SYSTEM_LOAD: "System Load (CPU/RAM/Disk)",
    MODE_TEMPERATURE: "Temperature Sensor",
    MODE_THROUGHPUT: "Network Throughput",
    MODE_ALERT: "Alert Flasher",
    MODE_GRAFANA: "Grafana / Generic Sensor",
}

FILL_OPTIONS = {
    FILL_LEFT_TO_RIGHT: "Left → Right",
    FILL_RIGHT_TO_LEFT: "Right → Left",
    FILL_CENTER_OUT: "Center → Out",
    FILL_EDGES_IN: "Edges → In",
}

FLASH_STYLE_OPTIONS = {
    "pulse": "Smooth Pulse",
    "strobe": "Hard Strobe",
    "solid": "Solid (no animation)",
}


class InfraGlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfraGlow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._wled_info: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — connect to WLED instance."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_WLED_HOST]
            self._port = user_input.get(CONF_WLED_PORT, DEFAULT_PORT)

            # Test connection
            client = WLEDClient(self._host, self._port)
            try:
                self._wled_info = await client.get_info()
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()

            if not errors:
                # Check if already configured
                await self.async_set_unique_id(
                    f"wled_viz_{self._host}_{self._port}"
                )
                self._abort_if_unique_id_configured()

                led_count = self._wled_info.get("leds", {}).get("count", "?")
                name = self._wled_info.get("name", self._host)

                return self.async_create_entry(
                    title=f"InfraGlow — {name} ({led_count} LEDs)",
                    data={
                        CONF_WLED_HOST: self._host,
                        CONF_WLED_PORT: self._port,
                        CONF_VISUALIZATIONS: [],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_WLED_HOST): str,
                    vol.Optional(CONF_WLED_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
            description_placeholders={
                "info": "Enter the IP address or hostname of your WLED device."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> InfraGlowOptionsFlow:
        """Get the options flow handler."""
        return InfraGlowOptionsFlow(config_entry)


class InfraGlowOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow — add/edit/remove visualizations."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._visualizations: list[dict[str, Any]] = list(
            config_entry.data.get(CONF_VISUALIZATIONS, [])
        )
        self._editing_index: int | None = None
        self._temp_mode: str | None = None
        self._next_viz_id: int = self._compute_next_id()

    def _compute_next_id(self) -> int:
        """Find the next unused visualization ID number."""
        existing = set()
        for viz in self._visualizations:
            vid = viz.get("id", "")
            if vid.startswith("viz_"):
                try:
                    existing.add(int(vid.split("_", 1)[1]))
                except ValueError:
                    pass
        n = 0
        while n in existing:
            n += 1
        return n

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the main options menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_viz()
            elif action == "done":
                return self._save_and_finish()
            elif action and action.startswith("edit_"):
                self._editing_index = int(action.split("_")[1])
                return await self.async_step_edit_viz()
            elif action and action.startswith("delete_"):
                idx = int(action.split("_")[1])
                if 0 <= idx < len(self._visualizations):
                    self._visualizations.pop(idx)
                return await self.async_step_init()

        # Build the menu
        action_options = {"add": "➕ Add Visualization"}

        for i, viz in enumerate(self._visualizations):
            name = viz.get("name", f"Visualization {i + 1}")
            mode = MODE_OPTIONS.get(viz.get("mode", ""), viz.get("mode", ""))
            entity = viz.get("entity_id", "?")
            action_options[f"edit_{i}"] = f"✏️ {name} ({mode} → {entity})"
            action_options[f"delete_{i}"] = f"🗑️ Delete: {name}"

        action_options["done"] = "✅ Save & Close"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(action_options),
                }
            ),
        )

    async def async_step_add_viz(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Add a new visualization."""
        if user_input is not None:
            mode = user_input["mode"]
            return await self.async_step_configure_viz(mode=mode)

        return self.async_show_form(
            step_id="add_viz",
            data_schema=vol.Schema(
                {
                    vol.Required("mode"): vol.In(MODE_OPTIONS),
                }
            ),
        )

    async def async_step_configure_viz(
        self,
        user_input: dict[str, Any] | None = None,
        mode: str | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure a visualization's settings."""
        if mode is None:
            mode = self._temp_mode
        if mode is None:
            return await self.async_step_init()

        if user_input is not None:
            # Build the visualization config
            defaults = MODE_DEFAULTS.get(mode, {})
            renderer_type = MODE_RENDERER_MAP.get(mode, RENDERER_GAUGE)

            viz_config = {
                "name": user_input.get("name", MODE_OPTIONS.get(mode, mode)),
                "mode": mode,
                "renderer_type": renderer_type,
                "entity_id": user_input["entity_id"],
                "segment_id": user_input.get("segment_id", 0),
                "num_leds": user_input.get("num_leds", 30),
                "floor": user_input.get("floor", defaults.get("floor", 0)),
                "ceiling": user_input.get("ceiling", defaults.get("ceiling", 100)),
                "update_interval": user_input.get("update_interval", DEFAULT_UPDATE_INTERVAL),
            }

            # Parse color inputs (hex → RGB list)
            if "color_low" in user_input:
                viz_config["color_low"] = _hex_to_rgb(user_input["color_low"])
            else:
                viz_config["color_low"] = DEFAULT_COLOR_LOW

            if "color_high" in user_input:
                viz_config["color_high"] = _hex_to_rgb(user_input["color_high"])
            else:
                viz_config["color_high"] = DEFAULT_COLOR_HIGH

            # Mode-specific settings
            if renderer_type == RENDERER_GAUGE:
                viz_config["fill_direction"] = user_input.get(
                    "fill_direction", FILL_LEFT_TO_RIGHT
                )
            elif renderer_type == RENDERER_ALERT:
                if "flash_color" in user_input:
                    viz_config["flash_color"] = _hex_to_rgb(user_input["flash_color"])
                else:
                    viz_config["flash_color"] = DEFAULT_FLASH_COLOR
                viz_config["flash_speed"] = user_input.get("flash_speed", 2.0)
                viz_config["flash_style"] = user_input.get("flash_style", "pulse")

            if self._editing_index is not None:
                self._visualizations[self._editing_index] = viz_config
                self._editing_index = None
            else:
                viz_config["id"] = f"viz_{self._next_viz_id}"
                self._next_viz_id += 1
                self._visualizations.append(viz_config)

            return await self.async_step_init()

        # Store mode for when form is submitted
        self._temp_mode = mode
        defaults = MODE_DEFAULTS.get(mode, {})
        renderer_type = MODE_RENDERER_MAP.get(mode, RENDERER_GAUGE)

        # Build schema based on mode
        schema_dict: dict[Any, Any] = {
            vol.Optional("name", default=MODE_OPTIONS.get(mode, "")): str,
            vol.Required("entity_id"): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor", "binary_sensor"] if mode == MODE_ALERT else ["sensor"],
                )
            ),
            vol.Optional("segment_id", default=0): vol.All(int, vol.Range(min=0)),
            vol.Optional("num_leds", default=30): vol.All(int, vol.Range(min=1, max=1000)),
        }

        if renderer_type != RENDERER_ALERT:
            schema_dict.update(
                {
                    vol.Optional("floor", default=defaults.get("floor", 0)): vol.Coerce(float),
                    vol.Optional("ceiling", default=defaults.get("ceiling", 100)): vol.Coerce(float),
                    vol.Optional("color_low", default="#00FF00"): str,
                    vol.Optional("color_high", default="#FF0000"): str,
                    vol.Optional("update_interval", default=DEFAULT_UPDATE_INTERVAL): vol.Coerce(float),
                }
            )

        if renderer_type == RENDERER_GAUGE:
            schema_dict[vol.Optional("fill_direction", default=FILL_LEFT_TO_RIGHT)] = vol.In(
                FILL_OPTIONS
            )

        if renderer_type == RENDERER_ALERT:
            schema_dict.update(
                {
                    vol.Optional("flash_color", default="#FF0000"): str,
                    vol.Optional("flash_speed", default=2.0): vol.Coerce(float),
                    vol.Optional("flash_style", default="pulse"): vol.In(FLASH_STYLE_OPTIONS),
                }
            )

        return self.async_show_form(
            step_id="configure_viz",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_edit_viz(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Edit an existing visualization."""
        if self._editing_index is not None and self._editing_index < len(self._visualizations):
            viz = self._visualizations[self._editing_index]
            mode = viz.get("mode", MODE_GRAFANA)
            return await self.async_step_configure_viz(mode=mode)
        return await self.async_step_init()

    def _save_and_finish(self) -> config_entries.ConfigFlowResult:
        """Save visualizations and close."""
        new_data = dict(self._config_entry.data)
        new_data[CONF_VISUALIZATIONS] = self._visualizations
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            data=new_data,
        )
        return self.async_create_entry(title="", data={})


def _hex_to_rgb(hex_color: str) -> list[int]:
    """Convert hex color string to RGB list."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return [255, 255, 255]
    try:
        return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [255, 255, 255]
