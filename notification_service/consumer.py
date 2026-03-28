"""Redis Streams consumer for the notification service."""
from __future__ import annotations

import asyncio
import json
import logging

import aiohttp
import redis.asyncio as aioredis

from notification_service.matcher import find_matching_subscribers
from notification_service.sender import send_telegram
from shared.config import settings
from shared.database import AsyncSessionLocal
from shared.events import EventType, ListingNewEvent

logger = logging.getLogger(__name__)

_BLOCK_MS = 5000   # block up to 5s waiting for new messages
_BATCH_SIZE = 10


async def consume(redis_client: aioredis.Redis, http: aiohttp.ClientSession) -> None:
    """Main consumer loop — reads listing.new events and dispatches notifications."""
    # Ensure consumer group exists
    try:
        await redis_client.xgroup_create(
            settings.stream_listings,
            settings.stream_consumer_group,
            id="0",
            mkstream=True,
        )
        logger.info("consumer: created group %s", settings.stream_consumer_group)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    consumer_name = "notif_worker_1"

    while True:
        try:
            messages = await redis_client.xreadgroup(
                groupname=settings.stream_consumer_group,
                consumername=consumer_name,
                streams={settings.stream_listings: ">"},
                count=_BATCH_SIZE,
                block=_BLOCK_MS,
            )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("consumer: read error: %s", exc)
            await asyncio.sleep(5)
            continue

        if not messages:
            continue

        for _stream, entries in messages:
            for msg_id, fields in entries:
                await _process_message(msg_id, fields, redis_client, http)


async def _process_message(
    msg_id: str,
    fields: dict,
    redis_client: aioredis.Redis,
    http: aiohttp.ClientSession,
) -> None:
    event_type = fields.get("event_type")
    if event_type != EventType.LISTING_NEW:
        await redis_client.xack(settings.stream_listings, settings.stream_consumer_group, msg_id)
        return

    try:
        payload = json.loads(fields["payload"])
        event = ListingNewEvent(**payload)
    except Exception as exc:
        logger.error("consumer: bad payload msg=%s: %s", msg_id, exc)
        await redis_client.xack(settings.stream_listings, settings.stream_consumer_group, msg_id)
        return

    async with AsyncSessionLocal() as session:
        try:
            matches = await find_matching_subscribers(session, event)
            tasks = [send_telegram(http, user, sub, event) for user, sub in matches]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug("consumer: msg=%s matched=%d", msg_id, len(matches))
        except Exception as exc:
            logger.exception("consumer: processing error msg=%s: %s", msg_id, exc)

    await redis_client.xack(settings.stream_listings, settings.stream_consumer_group, msg_id)
