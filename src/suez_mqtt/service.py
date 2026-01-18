"""Async Service - Using toutsurmoneau library (Fully Automated)"""

import asyncio
import logging
import signal
import sys
import threading
from datetime import datetime
from typing import Optional

from .client import SuezClient
from .publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class SuezMQTTService:
    """Async service that fetches water consumption data using toutsurmoneau library"""

    def __init__(self, email: str, password: str, id_pds: str,
                 mqtt_publisher: MQTTPublisher, verify_ssl: bool = True,
                 heartbeat_interval: int = 60):
        """
        Initialize service

        Args:
            email: Suez account email
            password: Suez account password
            id_pds: Point De Service ID (water meter ID)
            mqtt_publisher: MQTT publisher
            verify_ssl: Enable SSL verification
            heartbeat_interval: Heartbeat interval in seconds (default: 60)
        """
        self.email = email
        self.password = password
        self.id_pds = id_pds
        self.mqtt_publisher = mqtt_publisher
        self.verify_ssl = verify_ssl
        self.running = False
        self.trigger_topic = f"{mqtt_publisher.topic}/refresh"
        self.heartbeat_interval = heartbeat_interval
        self.suez_client = None

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def _on_trigger_message(self, client, userdata, msg):
        """Handle trigger message from MQTT"""
        logger.info(f"Received trigger on '{msg.topic}'")

        try:
            payload_raw = msg.payload.decode('utf-8').strip()

            # Try to parse as JSON first
            mode = 'daily'
            days = 30

            try:
                import json
                payload_json = json.loads(payload_raw)
                mode = payload_json.get('mode', 'daily').lower()
            except (json.JSONDecodeError, AttributeError):
                # Fall back to plain text parsing
                payload = payload_raw.lower()
                if payload == 'monthly':
                    mode = 'monthly'
                elif payload == 'history':
                    mode = 'history'
                elif payload in ['daily', '', 'refresh']:
                    mode = 'daily'
                else:
                    logger.warning(f"Unknown payload '{payload}', using daily mode")
                    mode = 'daily'

            # Set days based on mode
            if mode == 'monthly':
                days = 90
            elif mode == 'history':
                days = 720  # ~2 years of history
            else:
                mode = 'daily'  # Normalize mode
                days = 30

            logger.info(f"Processing request: mode={mode}, days={days}")

            # Run async function in a separate thread to avoid event loop issues
            # The MQTT callback is synchronous, so we need to spawn a thread
            thread = threading.Thread(
                target=self._run_async_in_thread,
                args=(mode, days),
                daemon=True
            )
            thread.start()

        except Exception as e:
            logger.error(f"Error handling trigger message: {e}")

    def _run_async_in_thread(self, mode: str, days: int):
        """Helper to run async function in a thread with its own event loop"""
        asyncio.run(self._async_fetch_and_publish(mode=mode, days=days))

    async def _async_fetch_and_publish(self, mode: str = 'daily', days: int = 30) -> bool:
        """
        Async fetch consumption data and publish to MQTT

        Args:
            mode: 'daily' or 'monthly'
            days: Number of days of history

        Returns:
            True if successful
        """
        logger.info("="*60)
        logger.info(f"Fetching {mode} consumption data...")
        logger.info("="*60)

        try:
            async with SuezClient(self.email, self.password, self.id_pds,
                                   self.verify_ssl) as client:

                # Check session
                if not await client.check_session():
                    logger.error("Authentication failed")
                    error_data = {
                        'error': 'auth_failed',
                        'message': 'Authentication failed'
                    }
                    self.mqtt_publisher.publish(error_data, f"{self.mqtt_publisher.topic}/error")
                    return False

                # Fetch data
                data = await client.get_consumption_data(mode=mode, days=days)

                if not data:
                    logger.error("Failed to retrieve consumption data")
                    error_data = {
                        'error': 'fetch_failed',
                        'message': 'Failed to retrieve consumption data'
                    }
                    self.mqtt_publisher.publish(error_data, f"{self.mqtt_publisher.topic}/error")
                    return False

                # Publish data
                if self.mqtt_publisher.publish(data):
                    logger.info("✓ Successfully published consumption data")

                    # Publish status
                    status_data = {
                        'status': 'success',
                        'mode': mode,
                        'records': len(data.get('data', {}).get('content', {}).get('measures', []))
                    }
                    self.mqtt_publisher.publish(status_data, f"{self.mqtt_publisher.topic}/status")
                    return True
                else:
                    logger.error("Failed to publish data to MQTT")
                    return False

        except Exception as e:
            logger.error(f"Error in fetch_and_publish: {e}")
            error_data = {
                'error': 'exception',
                'message': str(e)
            }
            self.mqtt_publisher.publish(error_data, f"{self.mqtt_publisher.topic}/error")
            return False

    def fetch_and_publish(self, mode: str = 'daily', days: int = 30) -> bool:
        """
        Synchronous wrapper for async fetch_and_publish

        Args:
            mode: 'daily' or 'monthly'
            days: Number of days of history

        Returns:
            True if successful
        """
        return asyncio.run(self._async_fetch_and_publish(mode, days))

    def _publish_heartbeat(self):
        """Publish a heartbeat message with current timestamp in milliseconds"""
        heartbeat_data = {
            'status': 'alive',
            'timestamp': int(datetime.now().timestamp() * 1000),
            'service': 'suez-mqtt'
        }
        self.mqtt_publisher.publish(heartbeat_data, f"{self.mqtt_publisher.topic}/heartbeat")

    async def _async_start_check(self) -> bool:
        """Async startup check"""
        logger.info("Checking authentication...")
        async with SuezClient(self.email, self.password, self.id_pds,
                               self.verify_ssl) as client:
            return await client.check_session()

    def start(self):
        """Start the service"""
        logger.info("="*60)
        logger.info("Suez to MQTT Service Starting (Fully Automated)")
        logger.info("="*60)
        logger.info("Using toutsurmoneau library - NO COOKIES NEEDED!")
        logger.info("="*60)

        # Check authentication on startup
        try:
            if not asyncio.run(self._async_start_check()):
                logger.error("")
                logger.error("="*60)
                logger.error("❌ AUTHENTICATION FAILED")
                logger.error("="*60)
                logger.error("")
                logger.error("Please check your credentials in .env:")
                logger.error("  SUEZ_EMAIL=your-email@example.com")
                logger.error("  SUEZ_PASSWORD=your-password")
                logger.error("  SUEZ_ID_PDS=your-meter-id")
                logger.error("")
                logger.error("="*60)
                sys.exit(1)
        except Exception as e:
            logger.error(f"Startup check failed: {e}")
            sys.exit(1)

        logger.info("✓ Authentication successful")

        # Connect to MQTT
        if not self.mqtt_publisher.connect():
            logger.error("Failed to connect to MQTT broker")
            sys.exit(1)

        # Wait for connection
        import time
        time.sleep(2)

        # Subscribe to trigger topic
        self.mqtt_publisher.subscribe(self.trigger_topic, self._on_trigger_message)

        logger.info("")
        logger.info("="*60)
        logger.info("✓ Service Ready (Fully Automated)")
        logger.info("="*60)
        logger.info(f"Listening for triggers on: {self.trigger_topic}")
        logger.info("")
        logger.info("To fetch data, publish to MQTT:")
        logger.info(f"  mosquitto_pub -t '{self.trigger_topic}' -m '{{\"mode\": \"daily\"}}'")
        logger.info("")
        logger.info("Payload formats:")
        logger.info(f"  JSON: {{\"mode\": \"daily\"}}, {{\"mode\": \"monthly\"}}, or {{\"mode\": \"history\"}}")
        logger.info(f"  Text: 'daily', 'monthly', or 'history' (backwards compatible)")
        logger.info("")
        logger.info("Mode descriptions:")
        logger.info(f"  daily   - Last 30 days of daily consumption")
        logger.info(f"  monthly - Recent months (last year + current year)")
        logger.info(f"  history - All available daily history (API-limited)")
        logger.info("")
        logger.info("✓ No cookies needed - Fully automated authentication!")
        logger.info(f"✓ Heartbeat publishing every {self.heartbeat_interval} seconds to: {self.mqtt_publisher.topic}/heartbeat")
        logger.info("="*60)

        self.running = True

        # Publish initial heartbeat
        self._publish_heartbeat()

        # Keep service running with periodic heartbeat
        heartbeat_counter = 0
        try:
            while self.running:
                time.sleep(1)
                heartbeat_counter += 1

                # Publish heartbeat at configured interval
                if heartbeat_counter >= self.heartbeat_interval:
                    self._publish_heartbeat()
                    heartbeat_counter = 0
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()

    def stop(self):
        """Stop the service"""
        if self.running:
            logger.info("Stopping service...")
            self.running = False
            self.mqtt_publisher.disconnect()
            logger.info("Service stopped")
