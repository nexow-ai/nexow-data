"""Market data poller - fetches prices and broadcasts via Redis."""

import asyncio
import json
from datetime import datetime

import redis.asyncio as redis
import structlog

from nexow_data.config import settings
from nexow_data.oanda import OandaClient

logger = structlog.get_logger(__name__)


class MarketDataPoller:
    """
    Polls Oanda API for live prices and broadcasts them via Redis pub/sub.
    
    This is the single point of contact with Oanda API to avoid rate limits.
    All other services subscribe to Redis for price updates.
    """

    def __init__(self):
        self.oanda = OandaClient()
        self.redis_client: redis.Redis | None = None
        self.running = False

    async def start(self):
        """Start the polling loop."""
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.running = True
        
        logger.info(
            "poller_started",
            instruments=settings.instruments,
            interval=settings.poll_interval_seconds,
        )
        
        try:
            while self.running:
                await self._poll_and_publish()
                await asyncio.sleep(settings.poll_interval_seconds)
        except Exception as e:
            logger.error("poller_error", error=str(e))
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the polling loop and cleanup."""
        self.running = False
        if self.redis_client:
            await self.redis_client.aclose()
        await self.oanda.close()
        logger.info("poller_stopped")

    async def _poll_and_publish(self):
        """Fetch prices from Oanda and publish to Redis."""
        try:
            # Fetch all prices in one API call
            prices = await self.oanda.get_prices(settings.instruments)
            
            # Create price update message
            message = {
                "timestamp": datetime.utcnow().isoformat(),
                "prices": prices,
            }
            
            # Publish to Redis channel
            message_json = json.dumps(message)
            await self.redis_client.publish(settings.redis_channel, message_json)
            
            logger.debug(
                "prices_published",
                instruments=list(prices.keys()),
                channel=settings.redis_channel,
            )
            
        except Exception as e:
            logger.error(
                "poll_failed",
                error=str(e),
                instruments=settings.instruments,
            )
