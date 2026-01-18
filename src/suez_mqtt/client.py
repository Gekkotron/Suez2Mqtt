"""Suez Client - Using toutsurmoneau library (NO CAPTCHA!)"""

import logging
import ssl
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any

import aiohttp
from toutsurmoneau import AsyncClient

logger = logging.getLogger(__name__)


class SuezClient:
    """
    Modern Suez client using the toutsurmoneau library

    This client works WITHOUT browser automation or CAPTCHA solving!
    Uses Laurent Martin's toutsurmoneau library which handles authentication automatically.
    """

    def __init__(self, email: str, password: str, id_pds: str, verify_ssl: bool = True):
        """
        Initialize Suez client

        Args:
            email: User email for toutsurmoneau.fr
            password: User password
            id_pds: Point De Service ID (water meter ID)
            verify_ssl: Enable SSL verification
        """
        self.email = email
        self.password = password
        self.id_pds = id_pds
        self.verify_ssl = verify_ssl

        # SSL context for requests
        self.ssl_context = None
        if not verify_ssl:
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            logger.warning("SSL verification is disabled")

        self._session = None
        self._client = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session and client are initialized"""
        if self._session is None:
            connector = aiohttp.TCPConnector(ssl=self.ssl_context) if not self.verify_ssl else None
            self._session = aiohttp.ClientSession(connector=connector)

            self._client = AsyncClient(
                username=self.email,
                password=self.password,
                meter_id=self.id_pds,
                session=self._session
            )

            logger.info("Initialized toutsurmoneau client")

    async def close(self):
        """Close the session"""
        if self._session:
            await self._session.close()
            self._session = None
            self._client = None

    async def check_session(self) -> bool:
        """
        Check if credentials are valid

        Returns:
            True if authenticated successfully
        """
        try:
            await self._ensure_session()
            result = await self._client.async_check_credentials()

            if result:
                logger.info("✓ Session is valid")
            else:
                logger.error("✗ Session is invalid")

            return result

        except Exception as e:
            logger.error(f"Session check failed: {e}")
            return False

    async def get_consumption_data(self, mode: str = 'daily', days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Retrieve consumption data

        Args:
            mode: 'daily', 'monthly', or 'history'
            days: Number of days of history

        Returns:
            Dictionary with consumption data or None if failed
        """
        try:
            await self._ensure_session()

            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            logger.info(f"Fetching {mode} consumption data ({start_date} to {end_date})")

            if mode == 'history':
                # Fetch historical data in monthly chunks to avoid API limits
                api_data = await self._fetch_historical_data(start_date, end_date)
            elif mode == 'monthly':
                # Get monthly data
                api_data = await self._client.async_monthly_recent()
            else:
                # Get daily data
                api_data = await self._client.async_telemetry('daily', start_date, end_date)

            # Format response to match your existing structure
            result = {
                'timestamp': datetime.now().isoformat(),
                'source': 'toutsurmoneau.fr',
                'id_pds': self.id_pds,
                'mode': mode,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'data': {
                    'content': {
                        'measures': api_data if isinstance(api_data, list) else [api_data]
                    }
                }
            }

            logger.info(f"✓ Successfully retrieved {mode} consumption data")
            return result

        except Exception as e:
            logger.error(f"Failed to retrieve consumption data: {e}")
            return None

    async def _fetch_historical_data(self, start_date: date, end_date: date) -> list:
        """
        Fetch historical daily data in monthly chunks to avoid API limits

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of all measures combined
        """
        all_measures = []
        current_start = start_date

        logger.info(f"Fetching historical data in monthly chunks from {start_date} to {end_date}")

        while current_start < end_date:
            # Calculate end of current chunk (end of month or end_date)
            current_end = min(
                date(current_start.year + (current_start.month // 12),
                     ((current_start.month % 12) + 1), 1) - timedelta(days=1),
                end_date
            )

            logger.info(f"  Fetching chunk: {current_start} to {current_end}")

            try:
                chunk_data = await self._client.async_telemetry('daily', current_start, current_end)
                if chunk_data and isinstance(chunk_data, list):
                    all_measures.extend(chunk_data)
                    logger.info(f"    Retrieved {len(chunk_data)} records")
            except Exception as e:
                logger.warning(f"    Failed to fetch chunk {current_start} to {current_end}: {e}")

            # Move to next month
            if current_start.month == 12:
                current_start = date(current_start.year + 1, 1, 1)
            else:
                current_start = date(current_start.year, current_start.month + 1, 1)

        logger.info(f"✓ Total historical records fetched: {len(all_measures)}")
        return all_measures

    async def get_monthly_data(self) -> Optional[Dict[str, Any]]:
        """
        Get monthly consumption data

        Returns:
            Dictionary with monthly consumption or None if failed
        """
        try:
            await self._ensure_session()
            monthly_data = await self._client.async_monthly_recent()

            logger.info("✓ Retrieved monthly consumption data")
            return monthly_data

        except Exception as e:
            logger.error(f"Failed to retrieve monthly data: {e}")
            return None

    async def get_daily_data(self, days: int = 30) -> Optional[list]:
        """
        Get daily consumption data

        Args:
            days: Number of days to retrieve

        Returns:
            List of daily consumption records or None if failed
        """
        try:
            await self._ensure_session()

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            daily_data = await self._client.async_telemetry('daily', start_date, end_date)

            logger.info(f"✓ Retrieved {len(daily_data)} daily records")
            return daily_data

        except Exception as e:
            logger.error(f"Failed to retrieve daily data: {e}")
            return None

    async def get_latest_reading(self) -> Optional[float]:
        """
        Get the latest meter reading

        Returns:
            Latest meter reading value or None if failed
        """
        try:
            await self._ensure_session()
            reading = await self._client.async_latest_meter_reading()

            logger.info(f"✓ Latest meter reading: {reading}")
            return reading

        except Exception as e:
            logger.error(f"Failed to retrieve latest reading: {e}")
            return None


# Convenience function for backwards compatibility
def create_client(email: str, password: str, id_pds: str, verify_ssl: bool = True) -> SuezClient:
    """
    Create a new Suez client instance

    Args:
        email: User email
        password: User password
        id_pds: Point De Service ID
        verify_ssl: Enable SSL verification

    Returns:
        SuezClient instance
    """
    return SuezClient(email, password, id_pds, verify_ssl)
