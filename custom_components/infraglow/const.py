"""Constants for InfraGlow."""

from homeassistant.const import Platform

DOMAIN = "infraglow"

PLATFORMS = [Platform.SENSOR, Platform.SELECT, Platform.NUMBER, Platform.SWITCH]

SUBENTRY_TYPE_VISUALIZATION = "visualization"

# Config keys (stored on config entry data)
CONF_WLED_HOST = "wled_host"
CONF_WLED_PORT = "wled_port"

# Visualization config keys (stored in subentry data)
CONF_VIZ_NAME = "name"
CONF_VIZ_MODE = "mode"
CONF_VIZ_RENDERER = "renderer_type"
CONF_VIZ_ENTITY_ID = "entity_id"
CONF_VIZ_SEGMENT_ID = "segment_id"
CONF_VIZ_NUM_LEDS = "num_leds"
CONF_VIZ_FLOOR = "floor"
CONF_VIZ_CEILING = "ceiling"
CONF_VIZ_COLOR_LOW = "color_low"
CONF_VIZ_COLOR_HIGH = "color_high"
CONF_VIZ_COLOR_MID = "color_mid"
CONF_VIZ_UPDATE_INTERVAL = "update_interval"
CONF_VIZ_FILL_DIRECTION = "fill_direction"
CONF_VIZ_INCLUDE_BLACK = "include_black"
CONF_VIZ_WLED_FX = "wled_fx"
CONF_VIZ_SPEED_MIN = "speed_min"
CONF_VIZ_SPEED_MAX = "speed_max"
CONF_VIZ_MIRROR = "mirror"
CONF_VIZ_ENABLED = "enabled"
CONF_VIZ_FLASH_COLOR = "flash_color"
CONF_VIZ_FLASH_SPEED = "flash_speed"

# Visualization modes
MODE_SYSTEM_LOAD = "system_load"
MODE_TEMPERATURE = "temperature"
MODE_THROUGHPUT = "throughput"
MODE_ALERT = "alert"
MODE_GRAFANA = "grafana"

# Renderer types
RENDERER_GAUGE = "gauge"
RENDERER_FLOW = "flow"
RENDERER_ALERT = "alert"
RENDERER_EFFECT = "effect"

# Mode -> default renderer mapping
MODE_RENDERER_MAP = {
    MODE_SYSTEM_LOAD: RENDERER_EFFECT,
    MODE_TEMPERATURE: RENDERER_EFFECT,
    MODE_THROUGHPUT: RENDERER_EFFECT,
    MODE_ALERT: RENDERER_ALERT,
    MODE_GRAFANA: RENDERER_EFFECT,
}

# Well-known WLED effect IDs for mode defaults
WLED_FX_SOLID = 0
WLED_FX_BREATHE = 2
WLED_FX_FIRE_2012 = 66
WLED_FX_COLORWAVES = 67
WLED_FX_PALETTE = 65
WLED_FX_GRADIENT = 46
WLED_FX_SCAN = 10
WLED_FX_RUNNING = 15

# Curated palette-friendly WLED effects (ID -> label)
EFFECT_OPTIONS: dict[int, str] = {
    0: "Solid",
    2: "Breathe",
    10: "Scan",
    15: "Running",
    46: "Gradient",
    65: "Palette",
    66: "Fire 2012",
    67: "Colorwaves",
    68: "BPM",
    69: "Fill Noise",
    75: "Lake",
    76: "Meteor",
    101: "Candle",
    108: "Phased",
    110: "Twinklecat",
}

# Mode-specific default effects
MODE_EFFECT_DEFAULTS = {
    MODE_SYSTEM_LOAD: {"fx": WLED_FX_BREATHE, "speed_min": 60, "speed_max": 240},
    MODE_TEMPERATURE: {"fx": WLED_FX_GRADIENT, "speed_min": 30, "speed_max": 200},
    MODE_THROUGHPUT: {"fx": WLED_FX_RUNNING, "speed_min": 20, "speed_max": 255},
    MODE_GRAFANA: {"fx": WLED_FX_BREATHE, "speed_min": 60, "speed_max": 240},
}

# Fill directions for gauge renderer
FILL_LEFT_TO_RIGHT = "left_to_right"
FILL_RIGHT_TO_LEFT = "right_to_left"
FILL_CENTER_OUT = "center_out"
FILL_EDGES_IN = "edges_in"

# Default values
DEFAULT_PORT = 80
DEFAULT_UPDATE_INTERVAL = 1.0
DEFAULT_EFFECT_UPDATE_INTERVAL = 0.5
DEFAULT_FLOOR = 0.0
DEFAULT_CEILING = 100.0
DEFAULT_COLOR_LOW = [0, 255, 0]
DEFAULT_COLOR_HIGH = [255, 0, 0]
DEFAULT_COLOR_MID = [255, 165, 0]
DEFAULT_FLASH_COLOR = [255, 0, 0]
DEFAULT_FLASH_SPEED = 2.0
DEFAULT_FILL_DIRECTION = FILL_LEFT_TO_RIGHT

# Mode-specific default floor/ceiling
MODE_DEFAULTS = {
    MODE_SYSTEM_LOAD: {"floor": 0, "ceiling": 100, "unit": "%"},
    MODE_TEMPERATURE: {"floor": 20, "ceiling": 90, "unit": "°C"},
    MODE_THROUGHPUT: {"floor": 0, "ceiling": 1000, "unit": "Mbps"},
    MODE_ALERT: {"floor": 0, "ceiling": 1},
    MODE_GRAFANA: {"floor": 0, "ceiling": 100, "unit": ""},
}

# WLED API
WLED_API_STATE = "/json/state"
WLED_API_INFO = "/json/info"

# Frontend
URL_BASE = "/infraglow"

INFRAGLOW_CARDS = [
    {
        "name": "InfraGlow Card",
        "filename": "infraglow-card.js",
        "version": "0.2.1",
    }
]
