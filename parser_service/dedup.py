"""Atomic upsert with dedup-hash collision handling.

Strategy:
  INSERT ... ON CONFLICT (dedup_hash) DO UPDATE SET seen_on = array_union(...)
  This is a single round-trip, serialisable via the unique index.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from parser_service.parsers.base import BaseParser, RawListing

# Raw SQL for atomic upsert — avoids ORM overhead and race conditions.
_UPSERT_SQL = text("""
INSERT INTO listings (
    id, source, source_id, source_url, seen_on, dedup_hash,
    title, description, city, address,
    latitude, longitude,
    rooms, area, floor, total_floors,
    price, currency, photos,
    extra_fields, status, created_at, updated_at
) VALUES (
    :id, :source, :source_id, :source_url, ARRAY[:source]::varchar(32)[], :dedup_hash,
    :title, :description, :city, :address,
    :latitude, :longitude,
    :rooms, :area, :floor, :total_floors,
    :price, :currency, :photos,
    :extra_fields::jsonb, 'active', now(), now()
)
ON CONFLICT (dedup_hash) DO UPDATE SET
    seen_on    = array(
                    SELECT DISTINCT unnest(
                        listings.seen_on || ARRAY[EXCLUDED.source]::varchar(32)[]
                    )
                 ),
    status     = 'active',
    updated_at = now()
RETURNING id, (xmax = 0) AS is_new
""")


async def upsert_listing(
    session: AsyncSession,
    raw: RawListing,
    current_source: str,
) -> tuple[uuid.UUID, bool]:
    """Insert or deduplicate a parsed listing.

    Args:
        session: Active async DB session (caller manages transaction).
        raw: Parsed listing from any parser.
        current_source: Source name (e.g. "avito").

    Returns:
        (listing_id, is_new) — is_new is True when a new row was inserted,
        False when an existing row was updated (dedup_hash collision).
    """
    dedup_hash = BaseParser.compute_dedup_hash(raw.address, raw.area, raw.price)
    listing_id = uuid.uuid4()

    import json
    result = await session.execute(
        _UPSERT_SQL,
        {
            "id": listing_id,
            "source": current_source,
            "source_id": raw.source_id,
            "source_url": raw.source_url,
            "dedup_hash": dedup_hash,
            "title": raw.title,
            "description": raw.description,
            "city": raw.city,
            "address": raw.address,
            "latitude": raw.latitude,
            "longitude": raw.longitude,
            "rooms": raw.rooms,
            "area": raw.area,
            "floor": raw.floor,
            "total_floors": raw.total_floors,
            "price": raw.price,
            "currency": raw.currency,
            "photos": raw.photos or [],
            "extra_fields": json.dumps(raw.extra_fields or {}),
        },
    )

    row = result.one()
    return row.id, row.is_new
