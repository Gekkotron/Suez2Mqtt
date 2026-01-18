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

## Features

✅ **Fully automated** - No cookies, no browser, no CAPTCHA
✅ **Async architecture** - Modern Python with asyncio
✅ **MQTT integration** - Trigger-based data fetching
✅ **Daily & monthly data** - Flexible consumption tracking

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
MQTT_TOPIC=water
HEARTBEAT_INTERVAL=60
```

## MQTT Topics

| Topic | Purpose | Payload |
|-------|---------|---------|
| `water/refresh` | Trigger fetch | `daily`, `monthly`, or `history` |
| `water/data` | Consumption data | JSON |
| `water/status` | Status messages | JSON |
| `water/error` | Error messages | JSON |
| `water/heartbeat` | Service alive indicator | JSON with timestamp |

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
mosquitto_pub -t 'water/refresh' -m '{"mode": "monthly"}'
```

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

```yaml
mqtt:
  button:
    - name: "Refresh Water Data"
      command_topic: "water/refresh"
      payload_press: "daily"

  sensor:
    - name: "Daily Water Usage"
      state_topic: "water/data"
      value_template: "{{ value_json.data.content.measures[-1].volume * 1000 | round(0) }}"
      unit_of_measurement: "L"
      device_class: "water"
```

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
SuezToMqtt/
├── src/suez_mqtt/
│   ├── client.py          # Async client using toutsurmoneau
│   ├── service.py         # Async MQTT service
│   ├── publisher.py       # MQTT publisher
│   └── __main__.py        # Entry point
├── tools/
│   └── test_client.py     # Test script
├── run.py                 # Launcher
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
    restart: unless-stopped
```

```bash
docker-compose up -d
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

## How It Works

This service uses the [toutsurmoneau](https://github.com/laurent-martin/py-mon-eau) library by Laurent Martin, which provides automated access to the Suez API without requiring:
- Manual cookie extraction
- Browser automation
- CAPTCHA solving

The library handles all authentication automatically using your email and password.

## License

Provided as-is for personal use.

## Credits

- **toutsurmoneau library**: [Laurent Martin](https://github.com/laurent-martin/py-mon-eau)
- **Home Assistant integration**: [hass_int_toutsurmoneau](https://github.com/laurent-martin/hass_int_toutsurmoneau)
