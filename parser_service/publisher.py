"""Redis Streams publisher for listing events."""
from __future__ import annotations

import redis.asyncio as redis

from shared.config import settings
from shared.events import ListingDeactivatedEvent, ListingNewEvent, ListingPurgedEvent


class EventPublisher:
    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def publish_new(self, event: ListingNewEvent) -> None:
        await self._redis.xadd(settings.stream_listings, event.to_stream_dict())

    async def publish_deactivated(self, event: ListingDeactivatedEvent) -> None:
        await self._redis.xadd(settings.stream_listings, event.to_stream_dict())

    async def publish_purged(self, event: ListingPurgedEvent) -> None:
        await self._redis.xadd(settings.stream_listings, event.to_stream_dict())
