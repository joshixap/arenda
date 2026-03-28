"""Notification Service entry point."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import redis.asyncio as aioredis

from notification_service.consumer import consume
from shared.config import settings
from shared.database import engine
from shared.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    connector = aiohttp.TCPConnector(limit=10)
    http = aiohttp.ClientSession(connector=connector)

    logger.info("Notification service started")
    try:
        await consume(redis_client, http)
    finally:
        await http.close()
        await redis_client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
