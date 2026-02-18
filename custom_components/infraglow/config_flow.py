"""Config flow for InfraGlow."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
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
    CONF_VIZ_INCLUDE_BLACK,
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
    EFFECT_OPTIONS,
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

EFFECT_SELECT_OPTIONS = [
    {"value": str(k), "label": v} for k, v in EFFECT_OPTIONS.items()
]

FLASH_STYLE_SELECT_OPTIONS = [
    {"value": "pulse", "label": "Smooth Pulse"},
    {"value": "strobe", "label": "Hard Strobe"},
    {"value": "solid", "label": "Solid (no animation)"},
]


class InfraGlowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfraGlow."""

    VERSION = 2

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._wled_info: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
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
                    f"infraglow_{self._host}_{self._port}"
                )
                self._abort_if_unique_id_configured()

                led_count = self._wled_info.get("leds", {}).get("count", "?")
                name = self._wled_info.get("name", self._host)

                return self.async_create_entry(
                    title=f"InfraGlow — {name} ({led_count} LEDs)",
                    data={
                        CONF_WLED_HOST: self._host,
                        CONF_WLED_PORT: self._port,
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry,
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {"visualization": VizSubentryFlow}


class VizSubentryFlow(ConfigSubentryFlow):
    """Flow for creating and editing visualization subentries."""

    def __init__(self) -> None:
        super().__init__()
        self._mode: str | None = None

    @property
    def _is_new(self) -> bool:
        return self.source == "user"

    # ── Create: step 1 — pick mode ────────────────────────────────

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        if user_input is not None:
            self._mode = user_input["mode"]
            return await self.async_step_configure()

        return self.async_show_form(
            step_id="user",
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

    # ── Create: step 2 — configure parameters ─────────────────────

    async def async_step_configure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        mode = self._mode
        if mode is None:
            return await self.async_step_user()

        if user_input is not None:
            data = _build_subentry_data(user_input, mode)
            title = user_input.get("name") or MODE_LABELS.get(mode, mode)
            return self.async_create_entry(title=title, data=data)

        schema = _build_viz_schema(mode)
        return self.async_show_form(
            step_id="configure",
            data_schema=schema,
            description_placeholders={"mode": MODE_LABELS.get(mode, mode)},
        )

    # ── Reconfigure — edit existing subentry ───────────────────────

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        existing = subentry.data
        mode = existing.get("mode", MODE_GRAFANA)

        if user_input is not None:
            data = _build_subentry_data(user_input, mode)
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data=data,
                title=user_input.get("name") or subentry.title,
            )

        schema = _build_viz_schema(mode)
        suggested = dict(existing)
        if "wled_fx" in suggested:
            suggested["wled_fx"] = str(suggested["wled_fx"])
        schema = self.add_suggested_values_to_schema(schema, suggested)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            description_placeholders={"mode": MODE_LABELS.get(mode, mode)},
        )


def _build_viz_schema(mode: str) -> vol.Schema:
    """Build the voluptuous schema for a visualization based on its mode."""
    renderer_type = MODE_RENDERER_MAP.get(mode, RENDERER_EFFECT)
    defaults = MODE_DEFAULTS.get(mode, {})
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
                vol.Required(CONF_VIZ_INCLUDE_BLACK, default=False): BooleanSelector(),
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


def _build_subentry_data(user_input: dict[str, Any], mode: str) -> dict[str, Any]:
    """Normalize and structure user input into subentry data."""
    renderer_type = MODE_RENDERER_MAP.get(mode, RENDERER_EFFECT)
    defaults = MODE_DEFAULTS.get(mode, {})

    data: dict[str, Any] = {
        "name": user_input.get("name") or MODE_LABELS.get(mode, mode),
        "mode": mode,
        "renderer_type": renderer_type,
        "entity_id": user_input["entity_id"],
        "segment_id": int(user_input.get("segment_id", 0)),
        "num_leds": int(user_input.get("num_leds", 30)),
        "enabled": True,
    }

    if renderer_type == RENDERER_EFFECT:
        mode_fx = MODE_EFFECT_DEFAULTS.get(mode, {})
        data.update(
            {
                "floor": float(user_input.get("floor", defaults.get("floor", 0))),
                "ceiling": float(user_input.get("ceiling", defaults.get("ceiling", 100))),
                "color_low": user_input.get("color_low", DEFAULT_COLOR_LOW),
                "color_high": user_input.get("color_high", DEFAULT_COLOR_HIGH),
                "wled_fx": int(user_input.get("wled_fx", mode_fx.get("fx", WLED_FX_BREATHE))),
                "wled_pal": 0,
                "speed_min": int(user_input.get("speed_min", mode_fx.get("speed_min", 60))),
                "speed_max": int(user_input.get("speed_max", mode_fx.get("speed_max", 240))),
                "mirror": bool(user_input.get("mirror", False)),
                CONF_VIZ_INCLUDE_BLACK: bool(user_input.get(CONF_VIZ_INCLUDE_BLACK, False)),
                "update_interval": float(
                    user_input.get("update_interval", DEFAULT_EFFECT_UPDATE_INTERVAL)
                ),
            }
        )

    elif renderer_type == RENDERER_ALERT:
        data.update(
            {
                "flash_color": user_input.get("flash_color", DEFAULT_FLASH_COLOR),
                "flash_speed": float(user_input.get("flash_speed", 2.0)),
                "flash_style": user_input.get("flash_style", "pulse"),
            }
        )

    return data
