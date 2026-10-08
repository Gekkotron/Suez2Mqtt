"""Home Assistant MQTT Discovery for Suez water consumption sensors.

Publishes retained discovery configs under
``<prefix>/sensor/<device_id>/<sensor>/config`` and the matching scalar state
values on ``<MQTT_TOPIC>/sensor/<sensor>``, so any MQTT Discovery client
(Home Assistant, the Oikos app) can pick up the sensors automatically.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from .publisher import MQTTPublisher

logger = logging.getLogger(__name__)


def _sanitize(value: str) -> str:
    """Keep only characters MQTT discovery allows in a node/object id."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned or "unknown"


class HomeAssistantDiscovery:
    """Builds and publishes HA MQTT discovery messages for Suez sensors."""

    SENSORS = ("daily_volume", "total_volume", "last_update")

    def __init__(
        self,
        publisher: MQTTPublisher,
        id_pds: str,
        prefix: str = "homeassistant",
        device_name: str = "Suez Water",
        base_state_topic: Optional[str] = None,
    ):
        self.publisher = publisher
        self.prefix = prefix.rstrip("/") or "homeassistant"
        self.device_name = device_name or "Suez Water"
        self.device_id = f"suez_water_{_sanitize(id_pds)}"
        self.base_state_topic = (base_state_topic or publisher.topic).rstrip("/")

    def state_topic(self, sensor: str) -> str:
        return f"{self.base_state_topic}/sensor/{sensor}"

    def _config_topic(self, sensor: str) -> str:
        return f"{self.prefix}/sensor/{self.device_id}/{sensor}/config"

    def _device_block(self) -> Dict[str, Any]:
        return {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "manufacturer": "Suez",
            "model": "Tout Sur Mon Eau",
        }

    def _configs(self) -> Dict[str, Dict[str, Any]]:
        device = self._device_block()
        return {
            "daily_volume": {
                "name": "Daily water consumption",
                "unique_id": f"{self.device_id}_daily_volume",
                "object_id": f"{self.device_id}_daily_volume",
                "state_topic": self.state_topic("daily_volume"),
                "unit_of_measurement": "L",
                "device_class": "water",
                "state_class": "measurement",
                "icon": "mdi:water",
                "device": device,
            },
            "total_volume": {
                "name": "Water meter reading",
                "unique_id": f"{self.device_id}_total_volume",
                "object_id": f"{self.device_id}_total_volume",
                "state_topic": self.state_topic("total_volume"),
                "unit_of_measurement": "m³",
                "device_class": "water",
                "state_class": "total_increasing",
                "icon": "mdi:water-pump",
                "device": device,
            },
            "last_update": {
                "name": "Last water reading",
                "unique_id": f"{self.device_id}_last_update",
                "object_id": f"{self.device_id}_last_update",
                "state_topic": self.state_topic("last_update"),
                "device_class": "timestamp",
                "icon": "mdi:clock-outline",
                "device": device,
            },
        }

    def publish_discovery(self) -> bool:
        """Publish retained discovery configs for every sensor."""
        logger.info(f"Publishing Home Assistant discovery under '{self.prefix}/'")
        ok = True
        for sensor, config in self._configs().items():
            payload = json.dumps(config, ensure_ascii=False)
            if not self.publisher.publish_raw(self._config_topic(sensor), payload, retain=True):
                ok = False
        if ok:
            logger.info(f"✓ Published discovery for device '{self.device_id}'")
        else:
            logger.warning("Some discovery messages failed to publish")
        return ok

    def clear_discovery(self) -> None:
        """Clear retained discovery messages (publish empty payloads)."""
        logger.info("Clearing Home Assistant discovery messages")
        for sensor in self._configs():
            self.publisher.publish_raw(self._config_topic(sensor), "", retain=True)

    def publish_states_from_data(self, data: Dict[str, Any]) -> None:
        """Extract scalar values from a Suez payload and publish them."""
        measures = (
            data.get("data", {}).get("content", {}).get("measures", [])
            if isinstance(data, dict)
            else []
        )
        # Suez lists the current day as a placeholder (index null, volume 0) until
        # the reading lands the next morning, so take the last day with a real index.
        latest = next(
            (
                m
                for m in reversed(measures)
                if isinstance(m, dict)
                and m.get("volume") is not None
                and m.get("index") is not None
            ),
            None,
        )
        if latest is None:
            logger.debug("No measure with a volume found; nothing to publish for discovery")
            return

        volume_m3 = latest.get("volume")
        if isinstance(volume_m3, (int, float)):
            liters = round(float(volume_m3) * 1000, 1)
            self.publisher.publish_raw(self.state_topic("daily_volume"), str(liters), retain=True)

        date_str = latest.get("date")
        if isinstance(date_str, str) and date_str:
            # Suez sends "YYYY-MM-DD HH:MM:SS" (or a bare date); HA timestamps need ISO 8601.
            iso = date_str.strip().replace(" ", "T", 1)
            if "T" not in iso:
                iso = f"{iso}T00:00:00"
            if not re.search(r"(Z|[+-]\d{2}:?\d{2})$", iso):
                iso = f"{iso}+00:00"
            self.publisher.publish_raw(self.state_topic("last_update"), iso, retain=True)

        # Some integrations expose a cumulative meter index in the measure itself.
        for key in ("index", "indexValue", "meter", "total"):
            index = latest.get(key)
            if isinstance(index, (int, float)):
                self.publisher.publish_raw(
                    self.state_topic("total_volume"), str(float(index)), retain=True
                )
                break

    def publish_meter_reading(self, value: Optional[float]) -> None:
        """Publish a cumulative meter reading (m³) coming from a dedicated API call."""
        if value is None:
            return
        try:
            as_float = float(value)
        except (TypeError, ValueError):
            logger.debug(f"Ignoring non-numeric meter reading: {value!r}")
            return
        self.publisher.publish_raw(self.state_topic("total_volume"), str(as_float), retain=True)
