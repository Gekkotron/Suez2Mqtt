"""Main entry point for Suez to MQTT service (Fully Automated)"""

import logging
import os
import sys
from dotenv import load_dotenv

from .publisher import MQTTPublisher
from .service import SuezMQTTService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function"""
    # Load environment variables
    load_dotenv()

    # Get configuration
    email = os.getenv('SUEZ_EMAIL')
    password = os.getenv('SUEZ_PASSWORD')
    id_pds = os.getenv('SUEZ_ID_PDS') or os.getenv('ID_PDS')
    verify_ssl = os.getenv('VERIFY_SSL', 'true').lower() in ('true', '1', 'yes')

    mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
    mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
    mqtt_username = os.getenv('MQTT_USERNAME')
    mqtt_password = os.getenv('MQTT_PASSWORD')
    mqtt_topic = os.getenv('MQTT_TOPIC', 'water')
    heartbeat_interval = int(os.getenv('HEARTBEAT_INTERVAL', '60'))

    # Validate configuration
    if not email:
        logger.error("SUEZ_EMAIL not configured in environment")
        logger.error("Set SUEZ_EMAIL environment variable in .env file")
        sys.exit(1)

    if not password:
        logger.error("SUEZ_PASSWORD not configured in environment")
        logger.error("Set SUEZ_PASSWORD environment variable in .env file")
        sys.exit(1)

    if not id_pds:
        logger.error("SUEZ_ID_PDS (or ID_PDS) not configured in environment")
        logger.error("Set SUEZ_ID_PDS environment variable in .env file")
        sys.exit(1)

    logger.info("="*60)
    logger.info("Configuration loaded:")
    logger.info(f"  Email: {email}")
    logger.info(f"  Meter ID: {id_pds}")
    logger.info(f"  SSL Verify: {verify_ssl}")
    logger.info(f"  MQTT Broker: {mqtt_broker}:{mqtt_port}")
    logger.info(f"  MQTT Topic: {mqtt_topic}")
    logger.info(f"  Heartbeat Interval: {heartbeat_interval}s")
    logger.info("="*60)

    # Create MQTT publisher
    mqtt_publisher = MQTTPublisher(
        broker=mqtt_broker,
        port=mqtt_port,
        username=mqtt_username,
        password=mqtt_password,
        topic=mqtt_topic
    )

    # Create and start service (fully automated)
    service = SuezMQTTService(
        email=email,
        password=password,
        id_pds=id_pds,
        mqtt_publisher=mqtt_publisher,
        verify_ssl=verify_ssl,
        heartbeat_interval=heartbeat_interval
    )

    service.start()


if __name__ == '__main__':
    main()
