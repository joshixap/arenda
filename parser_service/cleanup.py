"""Cleanup Worker — deletes inactive listings older than N days.

Runs daily at 03:00 via APScheduler.
Cascade ON DELETE in Favorite FK handles favorites cleanup automatically.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.models import Listing, ListingStatus

logger = logging.getLogger(__name__)


async def run_cleanup(session: AsyncSession, publisher) -> int:
    """Delete inactive listings older than settings.inactive_ttl_days.

    Returns number of deleted rows.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.inactive_ttl_days)

    # Collect IDs first for event publishing
    result = await session.execute(
        select(Listing.id).where(
            Listing.status == ListingStatus.INACTIVE,
            Listing.deactivated_at < cutoff,
        )
    )
    ids: list[uuid.UUID] = result.scalars().all()

    if not ids:
        logger.info("cleanup: nothing to delete")
        return 0

    await session.execute(
        delete(Listing).where(Listing.id.in_(ids))
    )
    await session.commit()

    logger.info("cleanup: deleted %d inactive listings older than %d days", len(ids), settings.inactive_ttl_days)

    if publisher:
        from shared.events import ListingPurgedEvent
        # Publish one aggregate event per cleanup run
        event = ListingPurgedEvent(
            listing_id=ids[0],  # representative id
            source="cleanup_worker",
            days_inactive=settings.inactive_ttl_days,
        )
        await publisher.publish_purged(event)

    return len(ids)
