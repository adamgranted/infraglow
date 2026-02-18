<div align="center">
  <a href="https://github.com/adamgranted/infraglow">
    <img src="" alt="InfraGlow Logo" height="80px" width="80px"/>
  </a>
  <h2>InfraGlow</h2>
  <p align="center">
      <p><b>Real-time infrastructure metrics on WLED LED strips for Home Assistant</b></p>
  </p>

  <p align="center">
    <a href="https://github.com/adamgranted/infraglow/blob/main/LICENSE">
      <img alt="license" src="https://img.shields.io/badge/license-MIT-blue">
    </a>
    <a href="https://github.com/hacs/integration">
      <img alt="hacs" src="https://img.shields.io/badge/HACS-Custom-orange">
    </a>
  </p>

</div>


<br>

InfraGlow is a [HACS](https://hacs.xyz/) integration that turns Home Assistant sensor data into real-time LED visualizations on [WLED](https://kno.wled.ge/) devices. Point it at a WLED instance, bind entities, and watch your LED strip become a living dashboard for CPU load, temperatures, network throughput, alerts, and more.


### Features
- **Gauge mode** — fill bar visualization with gradient colors for CPU%, RAM%, disk, temperatures
- **Flow mode** — animated pulses whose speed maps to the sensor value, ideal for network throughput
- **Alert mode** — binary override that takes over the entire strip with pulse/strobe/solid flash styles
- **Segment support** — run multiple visualizations on different WLED segments of the same strip
- **Floor/ceiling mapping** — normalizes any value range; low activity shows the bottom of your scale
- **Three-stop gradients** — optional mid-color for green → yellow → red style ramps
- **Full UI config** — no YAML required, everything through Home Assistant config flow and options flow


## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click **Integrations** → **⋮** → **Custom repositories**
3. Add `https://github.com/adamgranted/infraglow` with category **Integration**
4. Search for "InfraGlow" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/wled_visualizer` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant


## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **InfraGlow**
3. Enter your WLED device's IP address and click **Submit**
4. The integration connects and auto-detects your LED count

### Adding Visualizations

1. Open the integration's **Configure** page
2. Click **➕ Add Visualization**
3. Choose a mode:
   - **System Load** — gauge, 0-100% scale
   - **Temperature** — gauge, 20-90°C scale
   - **Network Throughput** — flow, 0-1000 Mbps scale
   - **Alert Flasher** — binary trigger
   - **Grafana / Generic** — gauge, custom floor/ceiling
4. Select the Home Assistant entity to watch
5. Set the WLED segment ID and LED count
6. Adjust floor, ceiling, colors, and mode-specific settings
7. Save — repeat for additional segments

### WLED Segment Prep

Before adding visualizations, configure segments in the WLED web UI:

1. Open your WLED device's web interface → **Segments**
2. Create segments for each zone (e.g., LEDs 0-29, 30-59, 60-89)
3. Note the segment IDs — you'll use them in InfraGlow


## Configuration Reference

### Universal Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Entity | HA entity to watch | (required) |
| Segment ID | WLED segment to render on | 0 |
| Number of LEDs | LED count in this segment | 30 |
| Floor | Minimum value (maps to 0%) | Mode-dependent |
| Ceiling | Maximum value (maps to 100%) | Mode-dependent |
| Low Color | Color at minimum value | `#00FF00` (green) |
| High Color | Color at maximum value | `#FF0000` (red) |
| Update Interval | Seconds between updates | 1.0 |

### Gauge Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Fill Direction | Left→Right, Right→Left, Center→Out, Edges→In | Left→Right |

### Alert Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Flash Color | Color of the alert flash | `#FF0000` (red) |
| Flash Speed | Pulse frequency in Hz | 2.0 |
| Flash Style | Smooth Pulse / Hard Strobe / Solid | Pulse |

When any alert visualization triggers, it overrides the **entire strip** regardless of segment assignments. Normal visualizations resume automatically when the alert entity returns to `off`.


## Entity Compatibility

**System Load** — [System Monitor](https://www.home-assistant.io/integrations/systemmonitor/) or [Glances](https://www.home-assistant.io/integrations/glances/): `sensor.processor_use`, `sensor.memory_use_percent`, `sensor.disk_use_percent`

**Temperature** — any sensor reporting temperature: `sensor.cpu_temperature`, `sensor.server_room_temperature`

**Network Throughput** — [UniFi](https://www.home-assistant.io/integrations/unifi/), [Speedtest](https://www.home-assistant.io/integrations/speedtest/), or SNMP sensors

**Alert Flasher** — any `binary_sensor` or entity reporting on/off

**Grafana / Generic** — create a [REST sensor](https://www.home-assistant.io/integrations/rest/) in HA that queries the Grafana API, then select it in InfraGlow


## Architecture

```
HA Entity States
       │
       ▼
┌──────────────────────┐
│  Coordinator         │  Watches entities, runs render loop @ 15fps
│  ┌────────────────┐  │
│  │ Gauge Renderer  │──┼──▶ WLED Segment 0  (system load)
│  │ Flow Renderer   │──┼──▶ WLED Segment 1  (throughput)
│  │ Gauge Renderer  │──┼──▶ WLED Segment 2  (temperature)
│  │ Alert Renderer  │──┼──▶ FULL STRIP OVERRIDE (when active)
│  └────────────────┘  │
└──────────┬───────────┘
           │
           ▼
     WLED JSON API
     POST /json/state
```


## Troubleshooting

**LEDs not updating** — check that the WLED device is reachable from your HA instance (HTTP, port 80 default).

**Visualization looks wrong** — verify floor/ceiling values match the entity's actual range. Check the entity state in HA Developer Tools.

**Alert won't clear** — ensure the `binary_sensor` entity returns to `off`. Check Developer Tools → States.

**Multiple devices** — add multiple InfraGlow instances, one per WLED device. Each manages its own visualizations independently.


## License

MIT
