"""Match a ListingNewEvent against active subscriptions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.events import ListingNewEvent
from shared.models import Subscription, User


async def find_matching_subscribers(
    session: AsyncSession, event: ListingNewEvent
) -> list[tuple[User, Subscription]]:
    """Return list of (user, subscription) pairs where the event matches the filter."""
    result = await session.execute(
        select(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .where(Subscription.is_active == True, User.is_active == True)  # noqa: E712
    )
    rows = result.all()

    matched = []
    for sub, user in rows:
        if _matches(event, sub):
            matched.append((user, sub))
    return matched


def _matches(event: ListingNewEvent, sub: Subscription) -> bool:
    if sub.filter_city and event.city.lower() != sub.filter_city.lower():
        return False
    if sub.filter_price_min and event.price < sub.filter_price_min:
        return False
    if sub.filter_price_max and event.price > sub.filter_price_max:
        return False
    if sub.filter_rooms_min and event.rooms is not None and event.rooms < sub.filter_rooms_min:
        return False
    if sub.filter_rooms_max and event.rooms is not None and event.rooms > sub.filter_rooms_max:
        return False
    if sub.filter_area_min and event.area is not None and event.area < sub.filter_area_min:
        return False
    if sub.filter_area_max and event.area is not None and event.area > sub.filter_area_max:
        return False
    if sub.filter_sources and event.source not in sub.filter_sources:
        return False
    return True
