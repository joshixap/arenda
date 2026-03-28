from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    telegram_id: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    telegram_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    added_at: datetime = Field(alias="created_at")

    model_config = {"from_attributes": True, "populate_by_name": True}


class SubscriptionCreate(BaseModel):
    name: str = Field(max_length=256)
    channel: str = "telegram"
    filter_city: str | None = None
    filter_rooms_min: int | None = None
    filter_rooms_max: int | None = None
    filter_price_min: int | None = None
    filter_price_max: int | None = None
    filter_area_min: float | None = None
    filter_area_max: float | None = None
    filter_sources: list[str] | None = None


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    filter_city: str | None = None
    filter_rooms_min: int | None = None
    filter_rooms_max: int | None = None
    filter_price_min: int | None = None
    filter_price_max: int | None = None
    filter_area_min: float | None = None
    filter_area_max: float | None = None
    filter_sources: list[str] | None = None


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    name: str
    channel: str
    is_active: bool
    filter_city: str | None
    filter_rooms_min: int | None
    filter_rooms_max: int | None
    filter_price_min: int | None
    filter_price_max: int | None
    filter_area_min: float | None
    filter_area_max: float | None
    filter_sources: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}
