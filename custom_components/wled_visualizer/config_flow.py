"""Config flow for InfraGlow."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorRGBSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

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
    RENDERER_ALERT,
    RENDERER_EFFECT,
    MODE_RENDERER_MAP,
    MODE_DEFAULTS,
    MODE_EFFECT_DEFAULTS,
    DEFAULT_COLOR_LOW,
    DEFAULT_COLOR_HIGH,
    DEFAULT_FLASH_COLOR,
    DEFAULT_EFFECT_UPDATE_INTERVAL,
    WLED_FX_BREATHE,
)
from .wled_client import WLEDClient

_LOGGER = logging.getLogger(__name__)

MODE_LABELS: dict[str, str] = {
    MODE_SYSTEM_LOAD: "System Load (CPU/RAM/Disk)",
    MODE_TEMPERATURE: "Temperature Sensor",
    MODE_THROUGHPUT: "Network Throughput",
    MODE_ALERT: "Alert Flasher",
    MODE_GRAFANA: "Grafana / Generic Sensor",
}

MODE_SELECT_OPTIONS = [
    {"value": k, "label": v} for k, v in MODE_LABELS.items()
]

# Curated subset of WLED effects that work well for metric visualization
EFFECT_SELECT_OPTIONS = [
    {"value": "0", "label": "Solid"},
    {"value": "2", "label": "Breathe"},
    {"value": "9", "label": "Rainbow"},
    {"value": "10", "label": "Scan"},
    {"value": "15", "label": "Running"},
    {"value": "46", "label": "Gradient"},
    {"value": "63", "label": "Pride 2015"},
    {"value": "65", "label": "Palette"},
    {"value": "66", "label": "Fire 2012"},
    {"value": "67", "label": "Colorwaves"},
    {"value": "68", "label": "BPM"},
    {"value": "69", "label": "Fill Noise"},
    {"value": "75", "label": "Lake"},
    {"value": "76", "label": "Meteor"},
    {"value": "101", "label": "Candle"},
    {"value": "108", "label": "Phased"},
    {"value": "110", "label": "Twinklecat"},
]

FLASH_STYLE_SELECT_OPTIONS = [
    {"value": "pulse", "label": "Smooth Pulse"},
    {"value": "strobe", "label": "Hard Strobe"},
    {"value": "solid", "label": "Solid (no animation)"},
]


class InfraGlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfraGlow."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._wled_info: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_WLED_HOST]
            self._port = int(user_input.get(CONF_WLED_PORT, DEFAULT_PORT))

            client = WLEDClient(self._host, self._port)
            try:
                self._wled_info = await client.get_info()
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()

            if not errors:
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
                    vol.Required(CONF_WLED_HOST): TextSelector(
                        TextSelectorConfig(type="text")
                    ),
                    vol.Optional(CONF_WLED_PORT, default=DEFAULT_PORT): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> InfraGlowOptionsFlow:
        return InfraGlowOptionsFlow(config_entry)


class InfraGlowOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow — add/edit/remove visualizations."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._visualizations: list[dict[str, Any]] = list(
            config_entry.data.get(CONF_VISUALIZATIONS, [])
        )
        self._editing_index: int | None = None
        self._temp_mode: str | None = None
        self._next_viz_id: int = self._compute_next_id()

    def _compute_next_id(self) -> int:
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

    # ── Menu ──────────────────────────────────────────────────────

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_viz":
                return await self.async_step_add_viz()
            if action == "edit_viz":
                return await self.async_step_edit_viz()
            if action == "delete_viz":
                return await self.async_step_delete_viz()
            if action == "save":
                return self._save_and_finish()

        options = [{"value": "add_viz", "label": "Add a visualization"}]
        if self._visualizations:
            options.append({"value": "edit_viz", "label": "Edit a visualization"})
            options.append({"value": "delete_viz", "label": "Remove a visualization"})
        options.append({"value": "save", "label": "Save and close"})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    # ── Add ───────────────────────────────────────────────────────

    async def async_step_add_viz(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._temp_mode = user_input["mode"]
            self._editing_index = None
            return await self.async_step_configure_viz()

        return self.async_show_form(
            step_id="add_viz",
            data_schema=vol.Schema(
                {
                    vol.Required("mode"): SelectSelector(
                        SelectSelectorConfig(
                            options=MODE_SELECT_OPTIONS,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    # ── Edit ──────────────────────────────────────────────────────

    async def async_step_edit_viz(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if not self._visualizations:
            return await self.async_step_init()

        if user_input is not None:
            idx = int(user_input["viz_index"])
            if 0 <= idx < len(self._visualizations):
                self._editing_index = idx
                self._temp_mode = self._visualizations[idx].get("mode", MODE_GRAFANA)
                return await self.async_step_configure_viz()
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_viz",
            data_schema=vol.Schema(
                {
                    vol.Required("viz_index"): SelectSelector(
                        SelectSelectorConfig(
                            options=self._viz_select_options(),
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    # ── Delete ────────────────────────────────────────────────────

    async def async_step_delete_viz(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if not self._visualizations:
            return await self.async_step_init()

        if user_input is not None:
            idx = int(user_input["viz_index"])
            if 0 <= idx < len(self._visualizations):
                removed = self._visualizations.pop(idx)
                _LOGGER.info("Removed visualization '%s'", removed.get("name"))
            return await self.async_step_init()

        return self.async_show_form(
            step_id="delete_viz",
            data_schema=vol.Schema(
                {
                    vol.Required("viz_index"): SelectSelector(
                        SelectSelectorConfig(
                            options=self._viz_select_options(),
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    # ── Configure ─────────────────────────────────────────────────

    async def async_step_configure_viz(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        mode = self._temp_mode
        if mode is None:
            return await self.async_step_init()

        if user_input is not None:
            return await self._process_viz_input(user_input, mode)

        defaults = MODE_DEFAULTS.get(mode, {})
        renderer_type = MODE_RENDERER_MAP.get(mode, RENDERER_EFFECT)
        schema = self._build_viz_schema(mode, renderer_type, defaults)

        if self._editing_index is not None and self._editing_index < len(self._visualizations):
            schema = self.add_suggested_values_to_schema(
                schema, self._visualizations[self._editing_index],
            )

        return self.async_show_form(
            step_id="configure_viz",
            data_schema=schema,
            description_placeholders={"mode": MODE_LABELS.get(mode, mode)},
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _viz_select_options(self) -> list[dict[str, str]]:
        options = []
        for i, viz in enumerate(self._visualizations):
            name = viz.get("name", f"Visualization {i + 1}")
            entity = viz.get("entity_id", "")
            label = f"{name} ({entity})" if entity else name
            options.append({"value": str(i), "label": label})
        return options

    def _build_viz_schema(
        self,
        mode: str,
        renderer_type: str,
        defaults: dict[str, Any],
    ) -> vol.Schema:
        mode_fx = MODE_EFFECT_DEFAULTS.get(mode, {})
        default_fx = str(mode_fx.get("fx", WLED_FX_BREATHE))

        schema_dict: dict[Any, Any] = {
            vol.Optional("name", default=MODE_LABELS.get(mode, "")): TextSelector(),
            vol.Required("entity_id"): EntitySelector(
                EntitySelectorConfig(
                    domain=(
                        ["sensor", "binary_sensor"]
                        if mode == MODE_ALERT
                        else ["sensor"]
                    ),
                )
            ),
            vol.Required("segment_id", default=0): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=31, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required("num_leds", default=30): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=1000, step=1, mode=NumberSelectorMode.BOX
                )
            ),
        }

        if renderer_type == RENDERER_EFFECT:
            schema_dict.update(
                {
                    vol.Required("floor", default=float(defaults.get("floor", 0))): NumberSelector(
                        NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)
                    ),
                    vol.Required("ceiling", default=float(defaults.get("ceiling", 100))): NumberSelector(
                        NumberSelectorConfig(mode=NumberSelectorMode.BOX, step=0.1)
                    ),
                    vol.Required("color_low", default=DEFAULT_COLOR_LOW): ColorRGBSelector(),
                    vol.Required("color_high", default=DEFAULT_COLOR_HIGH): ColorRGBSelector(),
                    vol.Required("wled_fx", default=default_fx): SelectSelector(
                        SelectSelectorConfig(
                            options=EFFECT_SELECT_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("speed_min", default=mode_fx.get("speed_min", 60)): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=255, step=1,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required("speed_max", default=mode_fx.get("speed_max", 240)): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=255, step=1,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required("mirror", default=False): BooleanSelector(),
                    vol.Required("update_interval", default=DEFAULT_EFFECT_UPDATE_INTERVAL): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1, max=10.0, step=0.1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                }
            )

        elif renderer_type == RENDERER_ALERT:
            schema_dict.update(
                {
                    vol.Required("flash_color", default=DEFAULT_FLASH_COLOR): ColorRGBSelector(),
                    vol.Required("flash_speed", default=2.0): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1, max=20.0, step=0.1,
                            mode=NumberSelectorMode.SLIDER,
                            unit_of_measurement="Hz",
                        )
                    ),
                    vol.Required("flash_style", default="pulse"): SelectSelector(
                        SelectSelectorConfig(
                            options=FLASH_STYLE_SELECT_OPTIONS,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )

        return vol.Schema(schema_dict)

    async def _process_viz_input(
        self,
        user_input: dict[str, Any],
        mode: str,
    ) -> config_entries.ConfigFlowResult:
        defaults = MODE_DEFAULTS.get(mode, {})
        renderer_type = MODE_RENDERER_MAP.get(mode, RENDERER_EFFECT)

        viz_config: dict[str, Any] = {
            "name": user_input.get("name") or MODE_LABELS.get(mode, mode),
            "mode": mode,
            "renderer_type": renderer_type,
            "entity_id": user_input["entity_id"],
            "segment_id": int(user_input.get("segment_id", 0)),
            "num_leds": int(user_input.get("num_leds", 30)),
        }

        if renderer_type == RENDERER_EFFECT:
            viz_config.update(
                {
                    "floor": float(user_input.get("floor", defaults.get("floor", 0))),
                    "ceiling": float(user_input.get("ceiling", defaults.get("ceiling", 100))),
                    "color_low": user_input.get("color_low", DEFAULT_COLOR_LOW),
                    "color_high": user_input.get("color_high", DEFAULT_COLOR_HIGH),
                    "wled_fx": int(user_input.get("wled_fx", WLED_FX_BREATHE)),
                    "wled_pal": 0,
                    "speed_min": int(user_input.get("speed_min", 60)),
                    "speed_max": int(user_input.get("speed_max", 240)),
                    "mirror": bool(user_input.get("mirror", False)),
                    "update_interval": float(
                        user_input.get("update_interval", DEFAULT_EFFECT_UPDATE_INTERVAL)
                    ),
                }
            )

        elif renderer_type == RENDERER_ALERT:
            viz_config.update(
                {
                    "flash_color": user_input.get("flash_color", DEFAULT_FLASH_COLOR),
                    "flash_speed": float(user_input.get("flash_speed", 2.0)),
                    "flash_style": user_input.get("flash_style", "pulse"),
                }
            )

        if self._editing_index is not None:
            viz_config["id"] = self._visualizations[self._editing_index].get(
                "id", f"viz_{self._next_viz_id}"
            )
            self._visualizations[self._editing_index] = viz_config
            self._editing_index = None
        else:
            viz_config["id"] = f"viz_{self._next_viz_id}"
            self._next_viz_id += 1
            self._visualizations.append(viz_config)

        return await self.async_step_init()

    def _save_and_finish(self) -> config_entries.ConfigFlowResult:
        new_data = dict(self._config_entry.data)
        new_data[CONF_VISUALIZATIONS] = self._visualizations
        self.hass.config_entries.async_update_entry(
            self._config_entry, data=new_data,
        )
        return self.async_create_entry(title="", data={})
