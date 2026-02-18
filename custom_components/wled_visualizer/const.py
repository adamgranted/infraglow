"""Constants for InfraGlow."""

DOMAIN = "wled_visualizer"

# Config keys
CONF_WLED_HOST = "wled_host"
CONF_WLED_PORT = "wled_port"
CONF_VISUALIZATIONS = "visualizations"

# Visualization config keys
CONF_VIZ_NAME = "name"
CONF_VIZ_MODE = "mode"
CONF_VIZ_RENDERER = "renderer_type"
CONF_VIZ_ENTITY_ID = "entity_id"
CONF_VIZ_SEGMENT_ID = "segment_id"
CONF_VIZ_FLOOR = "floor"
CONF_VIZ_CEILING = "ceiling"
CONF_VIZ_COLOR_LOW = "color_low"
CONF_VIZ_COLOR_HIGH = "color_high"
CONF_VIZ_COLOR_MID = "color_mid"
CONF_VIZ_UPDATE_INTERVAL = "update_interval"
CONF_VIZ_FILL_DIRECTION = "fill_direction"
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

# Mode → default renderer mapping
MODE_RENDERER_MAP = {
    MODE_SYSTEM_LOAD: RENDERER_GAUGE,
    MODE_TEMPERATURE: RENDERER_GAUGE,
    MODE_THROUGHPUT: RENDERER_FLOW,
    MODE_ALERT: RENDERER_ALERT,
    MODE_GRAFANA: RENDERER_GAUGE,
}

# Fill directions for gauge renderer
FILL_LEFT_TO_RIGHT = "left_to_right"
FILL_RIGHT_TO_LEFT = "right_to_left"
FILL_CENTER_OUT = "center_out"
FILL_EDGES_IN = "edges_in"

# Default values
DEFAULT_PORT = 80
DEFAULT_UPDATE_INTERVAL = 1.0  # seconds
DEFAULT_FLOOR = 0.0
DEFAULT_CEILING = 100.0
DEFAULT_COLOR_LOW = [0, 255, 0]       # Green
DEFAULT_COLOR_HIGH = [255, 0, 0]      # Red
DEFAULT_COLOR_MID = [255, 165, 0]     # Orange
DEFAULT_FLASH_COLOR = [255, 0, 0]     # Red
DEFAULT_FLASH_SPEED = 2.0             # Hz
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
