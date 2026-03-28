"""Inter-service event contracts published to Redis Streams."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, enum.Enum):
    LISTING_NEW = "listing.new"
    LISTING_UPDATED = "listing.updated"
    LISTING_DEACTIVATED = "listing.deactivated"
    LISTING_PURGED = "listing.purged"


class _BaseEvent(BaseModel):
    listing_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str

    def to_stream_dict(self) -> dict[str, str]:
        """Serialize for XADD — Redis Streams accept flat str→str maps."""
        return {
            "event_type": self.event_type,
            "payload": self.model_dump_json(),
        }


class ListingNewEvent(_BaseEvent):
    event_type: str = Field(default=EventType.LISTING_NEW, frozen=True)
    title: str
    city: str
    price: int
    rooms: int | None = None
    area: float | None = None
    source_url: str


class ListingUpdatedEvent(_BaseEvent):
    event_type: str = Field(default=EventType.LISTING_UPDATED, frozen=True)
    changed_fields: list[str]
    old_price: int | None = None
    new_price: int | None = None


class ListingDeactivatedEvent(_BaseEvent):
    event_type: str = Field(default=EventType.LISTING_DEACTIVATED, frozen=True)
    reason: str = "not_found_on_source"


class ListingPurgedEvent(_BaseEvent):
    event_type: str = Field(default=EventType.LISTING_PURGED, frozen=True)
    days_inactive: int
