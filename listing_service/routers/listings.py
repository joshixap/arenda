from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_service.schemas import ListingDetail, ListingMapItem, PaginatedListings
from listing_service.search.query_builder import (
    AreaFilter,
    CityFilter,
    FullTextFilter,
    ListingQueryBuilder,
    PageParams,
    PriceFilter,
    RoomsFilter,
    SortField,
    SourceFilter,
    StatusFilter,
)
from shared.database import get_session
from shared.models import Listing

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=PaginatedListings)
async def search_listings(
    city: str | None = None,
    q: str | None = None,
    rooms_min: int | None = None,
    rooms_max: int | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    area_min: float | None = None,
    area_max: float | None = None,
    source: Annotated[list[str] | None, Query()] = None,
    sort: SortField = SortField.DATE_DESC,
    page: int = 1,
    size: int = 20,
    session: AsyncSession = Depends(get_session),
):
    filters = [StatusFilter("active")]
    if city:
        filters.append(CityFilter(city))
    if q:
        filters.append(FullTextFilter(q))
    if rooms_min is not None or rooms_max is not None:
        filters.append(RoomsFilter(rooms_min, rooms_max))
    if price_min is not None or price_max is not None:
        filters.append(PriceFilter(price_min, price_max))
    if area_min is not None or area_max is not None:
        filters.append(AreaFilter(area_min, area_max))
    if source:
        filters.append(SourceFilter(source))

    builder = ListingQueryBuilder(filters=filters, sort=sort, page=PageParams(page=page, size=size))

    total_result = await session.execute(builder.build_count())
    total = total_result.scalar_one()

    items_result = await session.execute(builder.build())
    items = items_result.scalars().all()

    return PaginatedListings(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get("/map", response_model=list[ListingMapItem])
async def listings_map(
    city: str | None = None,
    lat_min: float | None = None,
    lat_max: float | None = None,
    lon_min: float | None = None,
    lon_max: float | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = (
        select(Listing)
        .where(Listing.status == "active", Listing.latitude.isnot(None), Listing.longitude.isnot(None))
    )
    if city:
        query = query.where(Listing.city.ilike(f"%{city}%"))
    if lat_min is not None:
        query = query.where(Listing.latitude >= lat_min)
    if lat_max is not None:
        query = query.where(Listing.latitude <= lat_max)
    if lon_min is not None:
        query = query.where(Listing.longitude >= lon_min)
    if lon_max is not None:
        query = query.where(Listing.longitude <= lon_max)

    result = await session.execute(query.limit(2000))
    return result.scalars().all()


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(listing_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing
