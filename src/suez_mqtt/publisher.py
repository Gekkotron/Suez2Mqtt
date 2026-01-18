"""MQTT Publisher - Handle MQTT publishing"""

import json
import logging
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT publisher for water consumption data"""
    
    def __init__(self, broker: str, port: int = 1883, 
                 username: Optional[str] = None, password: Optional[str] = None,
                 topic: str = "water"):
        """
        Initialize MQTT publisher
        
        Args:
            broker: MQTT broker hostname
            port: MQTT broker port
            username: MQTT username (optional)
            password: MQTT password (optional)
            topic: Base MQTT topic
        """
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        try:
            # Try new API (paho-mqtt >= 2.0)
            if hasattr(mqtt, 'CallbackAPIVersion'):
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            else:
                self.client = mqtt.Client()
        except Exception:
            # Fall back to old API
            self.client = mqtt.Client()
        
        if username and password:
            self.client.username_pw_set(username, password)
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False
        
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker {self.broker}:{self.port}")
            self.connected = True
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming MQTT messages"""
        logger.debug(f"Received message on {msg.topic}: {msg.payload}")
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")
    
    def publish(self, data: Dict[str, Any], topic: Optional[str] = None) -> bool:
        """
        Publish data to MQTT
        
        Args:
            data: Data to publish
            topic: Override default topic
            
        Returns:
            True if published successfully
        """
        try:
            publish_topic = topic or f"{self.topic}/data"
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            
            result = self.client.publish(publish_topic, payload, qos=1, retain=True)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published data to '{publish_topic}'")
                return True
            else:
                logger.error(f"Failed to publish, return code: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False
    
    def subscribe(self, topic: str, callback=None):
        """Subscribe to MQTT topic"""
        if callback:
            self.client.message_callback_add(topic, callback)
        self.client.subscribe(topic)
        logger.info(f"Subscribed to '{topic}'")
