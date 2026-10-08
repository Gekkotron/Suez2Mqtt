# Suez to MQTT

Fetch water consumption data from Suez Tout Sur Mon Eau and publish to MQTT - fully automated with no manual steps.

## Quick Start

```bash
# 1. Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure .env file
SUEZ_EMAIL=your-email@example.com
SUEZ_PASSWORD=your-password
SUEZ_ID_PDS=your-meter-id
MQTT_BROKER=localhost

# 3. Run
python run.py

# 4. Trigger data fetch
mosquitto_pub -t 'water/refresh' -m '{"mode": "daily"}'
```

Home Assistant and the [Oikos app](https://github.com/Gekkotron/Oikos) pick up
the water sensors automatically — see [Home Assistant discovery](#home-assistant-discovery).

## Features

✅ **Fully automated** - No cookies, no browser, no CAPTCHA
✅ **Async architecture** - Modern Python with asyncio
✅ **MQTT integration** - Trigger-based data fetching
✅ **Daily & monthly data** - Flexible consumption tracking
✅ **Home Assistant discovery** - Sensors appear automatically in HA and the [Oikos app](https://github.com/Gekkotron/Oikos) (toggle with `HA_DISCOVERY_ENABLED`)

## Configuration

Create a `.env` file:

```env
# Required
SUEZ_EMAIL=your-email@example.com
SUEZ_PASSWORD=your-password
SUEZ_ID_PDS=your-meter-id

# Optional
VERIFY_SSL=false
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_USERNAME=your-mqtt-user       # omit for anonymous broker
MQTT_PASSWORD=your-mqtt-password   # omit for anonymous broker
MQTT_TOPIC=water
HEARTBEAT_INTERVAL=60

# Home Assistant MQTT Discovery (optional, defaults shown)
HA_DISCOVERY_ENABLED=true
HA_DISCOVERY_PREFIX=homeassistant
HA_DEVICE_NAME=Suez Water
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `HA_DISCOVERY_ENABLED` | `true` | Publish retained Home Assistant MQTT discovery messages. Set to `false` to turn the integration off. |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Base topic HA (and the Oikos app) listens on for discovery. |
| `HA_DEVICE_NAME` | `Suez Water` | Device name shown in HA / Oikos. |

## MQTT Topics

| Topic | Purpose | Payload |
|-------|---------|---------|
| `water/refresh` | Trigger fetch | `daily`, `monthly`, or `history` |
| `water/data` | Consumption data | JSON |
| `water/status` | Status messages | JSON |
| `water/error` | Error messages (retained; cleared on next successful publish) | JSON |
| `water/heartbeat` | Service alive indicator | JSON with timestamp |
| `water/sensor/daily_volume` | Latest daily volume (L) | Scalar (used by HA discovery) |
| `water/sensor/total_volume` | Latest meter reading (m³) | Scalar (used by HA discovery) |
| `water/sensor/last_update` | Timestamp of the latest reading | ISO 8601 (used by HA discovery) |

### Home Assistant discovery

When `HA_DISCOVERY_ENABLED=true` (default), the service publishes retained
Home Assistant MQTT Discovery configs on startup:

| Topic | Sensor |
|-------|--------|
| `<HA_DISCOVERY_PREFIX>/sensor/suez_water_<id_pds>/daily_volume/config` | Daily water consumption (L, `device_class: water`, `state_class: measurement`) |
| `<HA_DISCOVERY_PREFIX>/sensor/suez_water_<id_pds>/total_volume/config` | Water meter reading (m³, `device_class: water`, `state_class: total_increasing`) |
| `<HA_DISCOVERY_PREFIX>/sensor/suez_water_<id_pds>/last_update/config` | Last reading timestamp (`device_class: timestamp`) |

State values are refreshed after every successful fetch triggered by
`water/refresh`.

To disable the integration completely (no discovery messages, no scalar state
topics), set `HA_DISCOVERY_ENABLED=false`.

### Oikos app

The [Oikos](https://github.com/Gekkotron/Oikos) app subscribes to the same
`homeassistant/#` discovery topics as Home Assistant: once discovery is
published, the Suez sensors show up automatically. To promote the daily volume
sensor to the Energy screen's water tile, open the Oikos *Customize* sheet and
set its role to `water`.

## Usage

### Start Service
```bash
python run.py
```

### Fetch Data

**JSON payload (recommended):**
```bash
# Daily data (last 30 days)
mosquitto_pub -t 'water/refresh' -m '{"mode": "daily"}'

# Monthly data (last 90 days)
mosquitto_pub -t 'water/refresh' -m '{"mode": "monthly"}'

# Historical data (last 720 days)
mosquitto_pub -t 'water/refresh' -m '{"mode": "history"}'

# One year of daily history (custom range)
mosquitto_pub -t 'water/refresh' -m '{"mode": "history", "days": 365}'
```

The JSON payload accepts an optional `days` field that overrides the mode
default (daily=30, monthly=90, history=720). Use it to request any custom
window, e.g. `{"mode": "history", "days": 365}` for the last year.

**Plain text payload (backwards compatible):**
```bash
# Daily data
mosquitto_pub -t 'water/refresh' -m 'daily'

# Monthly data
mosquitto_pub -t 'water/refresh' -m 'monthly'

# Historical data
mosquitto_pub -t 'water/refresh' -m 'history'
```

### Subscribe to Data
```bash
mosquitto_sub -t 'water/#' -v
```

### Monitor Service Heartbeat
The service publishes a heartbeat message every 60 seconds (configurable via `HEARTBEAT_INTERVAL`):

```bash
mosquitto_sub -t 'water/heartbeat' -v
```

Heartbeat payload example:
```json
{
  "status": "alive",
  "timestamp": 1737235845123,
  "service": "suez-mqtt"
}
```

The timestamp is in milliseconds since Unix epoch (January 1, 1970).


## Integration Examples

### Home Assistant

With `HA_DISCOVERY_ENABLED=true` (the default), the sensors appear
automatically under a `Suez Water` device — no YAML needed. You only need to
add a button to trigger the refresh:

```yaml
mqtt:
  button:
    - name: "Refresh Water Data"
      command_topic: "water/refresh"
      payload_press: '{"mode": "daily"}'
```

<details>
<summary>Manual configuration (when discovery is disabled)</summary>

If you set `HA_DISCOVERY_ENABLED=false`, you can still declare the sensors
yourself from the published scalar topics (`water/sensor/*`):

```yaml
mqtt:
  sensor:
    - name: "Suez daily volume"
      state_topic: "water/sensor/daily_volume"
      unit_of_measurement: "L"
      device_class: "water"
      state_class: "measurement"
    - name: "Suez meter reading"
      state_topic: "water/sensor/total_volume"
      unit_of_measurement: "m³"
      device_class: "water"
      state_class: "total_increasing"
    - name: "Suez last reading"
      state_topic: "water/sensor/last_update"
      device_class: "timestamp"
```

Or parse the raw JSON on `water/data` directly:

```yaml
mqtt:
  sensor:
    - name: "Daily Water Usage"
      state_topic: "water/data"
      value_template: "{{ value_json.data.content.measures[-1].volume * 1000 | round(0) }}"
      unit_of_measurement: "L"
      device_class: "water"
```

</details>

### Node-RED

```javascript
// MQTT In node subscribed to 'water/data'
// Function node:
const measures = msg.payload.data.content.measures;
const latest = measures[measures.length - 1];
msg.payload = {
    volume_liters: latest.volume * 1000,
    date: latest.date
};
return msg;
```

## Project Structure

```
Suez2Mqtt/
├── src/suez_mqtt/
│   ├── client.py          # Async client using toutsurmoneau
│   ├── service.py         # Async MQTT service
│   ├── publisher.py       # MQTT publisher
│   ├── discovery.py       # Home Assistant MQTT discovery
│   └── __main__.py        # Entry point
├── run.py                 # Launcher
├── update.sh              # git pull --rebase + docker compose rebuild
├── docker-compose.yml     # Docker Compose service definition
├── Dockerfile             # Container image
├── requirements.txt       # Dependencies
└── .env                   # Configuration
```

## Dependencies

- `toutsurmoneau>=0.0.27` - Suez API client
- `aiohttp>=3.13.0` - Async HTTP
- `paho-mqtt>=1.6.1` - MQTT client
- `python-dotenv>=1.0.0` - Environment variables

## Docker

```yaml
# docker-compose.yml
version: '3'
services:
  suez-mqtt:
    build: .
    environment:
      - SUEZ_EMAIL=your-email@example.com
      - SUEZ_PASSWORD=your-password
      - SUEZ_ID_PDS=your-meter-id
      - MQTT_BROKER=mosquitto
      # Home Assistant discovery (optional, defaults shown)
      - HA_DISCOVERY_ENABLED=true
      - HA_DISCOVERY_PREFIX=homeassistant
      - HA_DEVICE_NAME=Suez Water
    restart: unless-stopped
```

```bash
# First run
docker compose up -d          # or: docker-compose up -d

# Update to latest master and rebuild
./update.sh
```

## Troubleshooting

### Authentication Failed
```bash
# Check credentials
cat .env | grep SUEZ
```

### MQTT Not Working
```bash
# Test MQTT broker
mosquitto_sub -t 'test' -h YOUR_BROKER

# Check config
cat .env | grep MQTT
```

### SSL Errors
Set `VERIFY_SSL=false` in `.env`

### Home Assistant / Oikos sensors don't show up

1. Confirm `HA_DISCOVERY_ENABLED=true` (the default) and that the service
   connected to the broker — the startup log prints
   `Publishing Home Assistant discovery under '<prefix>/'`.
2. In Home Assistant, make sure the MQTT integration's discovery prefix
   matches `HA_DISCOVERY_PREFIX` (default `homeassistant`).
3. Check the retained config topic exists on the broker:
   ```bash
   mosquitto_sub -t 'homeassistant/sensor/suez_water_<id_pds>/+/config' -v
   ```
4. The sensors show the last published value — trigger a refresh at least
   once with `mosquitto_pub -t 'water/refresh' -m '{"mode": "daily"}'`.
5. In Oikos specifically, open *Customize* on the sensor and set its energy
   role to `water` so it joins the Energy screen's water tile.

## How It Works

This service uses the [toutsurmoneau](https://github.com/laurent-martin/py-mon-eau) library by Laurent Martin, which provides automated access to the Suez API without requiring:
- Manual cookie extraction
- Browser automation
- CAPTCHA solving

The library handles all authentication automatically using your email and password.

On startup — when `HA_DISCOVERY_ENABLED=true` — the service publishes retained
Home Assistant MQTT Discovery configs under `<HA_DISCOVERY_PREFIX>/sensor/suez_water_<id_pds>/…/config`.
Each refresh triggered by `water/refresh` then extracts the latest measure
from the Suez response and publishes scalar state values on
`<MQTT_TOPIC>/sensor/<name>`. Both Home Assistant and the
[Oikos](https://github.com/Gekkotron/Oikos) app subscribe to the same
discovery tree, so the sensors appear in both without extra configuration.

## License

Provided as-is for personal use.

## Credits

- **toutsurmoneau library**: [Laurent Martin](https://github.com/laurent-martin/py-mon-eau)
- **Home Assistant integration**: [hass_int_toutsurmoneau](https://github.com/laurent-martin/hass_int_toutsurmoneau)
