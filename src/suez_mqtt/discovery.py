"""Home Assistant MQTT Discovery for Suez water consumption sensors.

Publishes retained discovery configs under
``<prefix>/sensor/<device_id>/<sensor>/config`` and the matching state values,
so any MQTT Discovery client (Home Assistant, the Oikos app) can pick up the
sensors automatically.

State goes either to scalar topics ``<MQTT_TOPIC>/sensor/<sensor>`` (default)
or, when ``json_state_topic`` is set, to a single retained JSON object
``{"consumption_l", "index_m3", "timestamp"}`` read through ``value_json``
templates. The JSON form is what history recorders such as Athena-Core store.
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
    # Key of each sensor in the JSON state object.
    JSON_KEYS = {"daily_volume": "consumption_l", "total_volume": "index_m3", "last_update": "timestamp"}

    def __init__(
        self,
        publisher: MQTTPublisher,
        id_pds: str,
        prefix: str = "homeassistant",
        device_name: str = "Suez Water",
        base_state_topic: Optional[str] = None,
        json_state_topic: Optional[str] = None,
    ):
        self.publisher = publisher
        self.prefix = prefix.rstrip("/") or "homeassistant"
        self.device_name = device_name or "Suez Water"
        self.device_id = f"suez_water_{_sanitize(id_pds)}"
        self.base_state_topic = (base_state_topic or publisher.topic).rstrip("/")
        self.json_state_topic = (json_state_topic or "").strip().rstrip("/") or None
        self._state: Dict[str, Any] = {}

    def state_topic(self, sensor: str) -> str:
        if self.json_state_topic:
            return self.json_state_topic
        return f"{self.base_state_topic}/sensor/{sensor}"

    def _state_fields(self, sensor: str) -> Dict[str, Any]:
        fields: Dict[str, Any] = {"state_topic": self.state_topic(sensor)}
        if self.json_state_topic:
            fields["value_template"] = f"{{{{ value_json.{self.JSON_KEYS[sensor]} }}}}"
        return fields

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
                **self._state_fields("daily_volume"),
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
                **self._state_fields("total_volume"),
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
                **self._state_fields("last_update"),
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
        """Extract the latest values from a Suez payload; ``flush_states`` publishes them."""
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
            self._state["daily_volume"] = round(float(volume_m3) * 1000, 1)

        date_str = latest.get("date")
        if isinstance(date_str, str) and date_str:
            # Suez sends "YYYY-MM-DD HH:MM:SS" (or a bare date); HA timestamps need ISO 8601.
            iso = date_str.strip().replace(" ", "T", 1)
            if "T" not in iso:
                iso = f"{iso}T00:00:00"
            if not re.search(r"(Z|[+-]\d{2}:?\d{2})$", iso):
                iso = f"{iso}+00:00"
            self._state["last_update"] = iso

        # Some integrations expose a cumulative meter index in the measure itself.
        for key in ("index", "indexValue", "meter", "total"):
            index = latest.get(key)
            if isinstance(index, (int, float)):
                self._state["total_volume"] = float(index)
                break

    def publish_meter_reading(self, value: Optional[float]) -> None:
        """Record a cumulative meter reading (m³) from a dedicated API call; ``flush_states`` publishes it."""
        if value is None:
            return
        try:
            as_float = float(value)
        except (TypeError, ValueError):
            logger.debug(f"Ignoring non-numeric meter reading: {value!r}")
            return
        self._state["total_volume"] = as_float

    def flush_states(self) -> None:
        """Publish the collected values: one JSON object, or one scalar topic per sensor."""
        if not self._state:
            return
        if self.json_state_topic:
            payload = {self.JSON_KEYS[k]: v for k, v in self._state.items()}
            self.publisher.publish_raw(self.json_state_topic, json.dumps(payload), retain=True)
            return
        for sensor, value in self._state.items():
            self.publisher.publish_raw(self.state_topic(sensor), str(value), retain=True)
