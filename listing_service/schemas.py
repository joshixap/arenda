from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ListingShort(BaseModel):
    id: uuid.UUID
    source: str
    source_url: str
    seen_on: list[str]
    title: str
    city: str
    address: str
    price: int
    rooms: int | None
    area: float | None
    floor: int | None
    latitude: float | None
    longitude: float | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListingDetail(ListingShort):
    source_id: str
    description: str | None
    total_floors: int | None
    photos: list[str] | None
    extra_fields: dict | None
    dedup_hash: str


class ListingMapItem(BaseModel):
    id: uuid.UUID
    latitude: float
    longitude: float
    price: int
    rooms: int | None
    title: str

    model_config = {"from_attributes": True}


class PaginatedListings(BaseModel):
    items: list[ListingShort]
    total: int
    page: int
    size: int
    pages: int
