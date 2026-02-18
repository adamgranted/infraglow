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

InfraGlow uses WLED's native effect engine for animations. Rather than pushing per-pixel data, it maps sensor values to WLED effect parameters (color, speed, intensity) so you get real movement and smooth transitions while the sensor value drives the look. Designed for square rack perimeter installs but works on any WLED strip.


### Features
- **Native WLED effects** — uses WLED's built-in animations (Breathe, Gradient, Running, Fire, Colorwaves, etc.) for real movement instead of static fills
- **Value-driven color** — sensor value picks a single color from the low-to-high gradient and maps it to WLED's three color slots for a cohesive palette
- **Speed mapping** — low sensor values = slow animation, high values = fast; the strip visually reflects intensity
- **Alert mode** — binary override that takes over the entire strip with pulse/strobe/solid flash styles
- **Segment support** — run multiple visualizations on different WLED segments of the same strip
- **Black insertion** — optional toggle to insert black between the two generated palette colors for higher contrast and more dramatic movement
- **Mirror toggle** — symmetrical animations for rack loop installs
- **Curated effect list** — only palette-friendly WLED effects are offered (rainbow/pride-style effects that ignore your colors are excluded)
- **Full UI config** — no YAML required, everything through Home Assistant config flow and options flow


## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=adamgranted&repository=infraglow&category=integration)

1. Open HACS in Home Assistant
2. Click **Integrations** → **⋮** → **Custom repositories**
3. Add `https://github.com/adamgranted/infraglow` with category **Integration**
4. Search for "InfraGlow" and install
5. Restart Home Assistant

### Manual

1. Download the latest release from GitHub
2. Copy the `custom_components/wled_visualizer` folder to your Home Assistant's `config/custom_components/` directory
3. Restart Home Assistant


## Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **InfraGlow**
3. Enter your WLED device's IP address and click **Submit**
4. The integration connects and auto-detects your LED count

### Adding Visualizations

1. Open the integration's **Configure** page
2. Select **Add a visualization**
3. Choose a mode:
   - **System Load** — Breathe effect, 0-100% scale
   - **Temperature** — Gradient effect, 20-90°C scale
   - **Network Throughput** — Running effect, 0-1000 Mbps scale
   - **Alert Flasher** — binary trigger, full-strip override
   - **Grafana / Generic** — Breathe effect, custom floor/ceiling
4. Select the Home Assistant entity to watch
5. Set the WLED segment ID and LED count
6. Pick a WLED effect, adjust colors, speed range, and mirror
7. Save — repeat for additional segments

### WLED Segment Prep

Before adding visualizations, configure segments in the WLED web UI:

1. Open your WLED device's web interface → **Segments**
2. Create segments for each zone (e.g., LEDs 0-29, 30-59, 60-89)
3. Note the segment IDs — you'll use them in InfraGlow


## Configuration Reference

### Metric Settings (System Load, Temperature, Throughput, Generic)

| Setting | Description | Default |
|---------|-------------|---------|
| Entity | HA sensor entity to watch | (required) |
| Segment ID | WLED segment to render on | 0 |
| Number of LEDs | LED count in this segment | 30 |
| Floor | Sensor value that maps to 0% | Mode-dependent |
| Ceiling | Sensor value that maps to 100% | Mode-dependent |
| Cool / Low Color | LED color at the floor value | Green |
| Hot / High Color | LED color at the ceiling value | Red |
| WLED Effect | Animation effect (Breathe, Gradient, Running, etc.) | Mode-dependent |
| Minimum Speed | Effect speed at the floor value (0-255) | Mode-dependent |
| Maximum Speed | Effect speed at the ceiling value (0-255) | Mode-dependent |
| Mirror | Mirror the animation for symmetrical rack loops | Off |
| Include Black | Insert black between the two palette colors for higher contrast | Off |
| Update Interval | How often to push updates to WLED | 0.5s |

### Alert Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Flash Color | Color of the alert flash | Red |
| Flash Speed | Pulse frequency in Hz | 2.0 |
| Flash Style | Smooth Pulse / Hard Strobe / Solid | Pulse |

When any alert visualization triggers, it overrides the **entire strip** regardless of segment assignments. Normal visualizations resume automatically when the alert entity returns to `off`.

### How Value Mapping Works

InfraGlow normalizes your sensor value to a 0.0-1.0 range using the floor/ceiling you set. That normalized value then drives:

- **Color** — picks a position on your low-to-high color gradient. Three color slots are generated with a wide spread (±30% on the gradient) so effects that use multiple colors show visually distinct movement. If **Include Black** is enabled, the tuple becomes `[primary, black, secondary]` for maximum contrast.
- **Speed** — linearly maps from your minimum to maximum speed setting. Low temp = gentle movement, high temp = fast.
- **Intensity** — also scales with the value for effects that use it.

This means your strip shows a cohesive palette that shifts from cool to hot as the sensor changes, with enough spread between the generated colors that WLED effects produce visible movement and contrast.


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
┌──────────────────────────┐
│  Coordinator             │  Watches entities, pushes updates
│  ┌────────────────────┐  │
│  │ Effect Renderer     │──┼──▶ WLED Segment 0  fx/pal/sx/ix/col
│  │ Effect Renderer     │──┼──▶ WLED Segment 1  fx/pal/sx/ix/col
│  │ Effect Renderer     │──┼──▶ WLED Segment 2  fx/pal/sx/ix/col
│  │ Alert Renderer      │──┼──▶ FULL STRIP OVERRIDE (per-pixel)
│  └────────────────────┘  │
└──────────┬───────────────┘
           │
           ▼
     WLED JSON API
     POST /json/state
```

Metric visualizations send native WLED effect parameters (~100 bytes per update) instead of per-pixel data (~2.7 KB per frame), reducing bandwidth by ~96% and letting WLED's own animation engine handle rendering.


## Troubleshooting

**LEDs not updating** — check that the WLED device is reachable from your HA instance (HTTP, port 80 default).

**Colors don't match** — verify floor/ceiling values match the entity's actual range. Check the entity state in HA Developer Tools.

**Effect not animating** — make sure you're not using the Solid effect (ID 0). Try Breathe or Gradient for visible movement.

**Alert won't clear** — ensure the `binary_sensor` entity returns to `off`. Check Developer Tools → States.

**Multiple devices** — add multiple InfraGlow instances, one per WLED device. Each manages its own visualizations independently.


## License

MIT
