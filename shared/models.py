"""SQLAlchemy 2.0 async models — shared across services via read-only import."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PURGED = "purged"


class SubscriptionChannel(str, enum.Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    PUSH = "push"


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------

class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # --- origin ---
    source: Mapped[str] = mapped_column(String(32), nullable=False, comment="First source that found this listing")
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="ID on the origin platform")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    seen_on: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default="{}",
        comment="All platforms where this listing was seen",
    )

    # --- dedup ---
    dedup_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True,
    )

    # --- listing data ---
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    rooms: Mapped[int | None] = mapped_column(Integer)
    area: Mapped[float | None] = mapped_column(Float)
    floor: Mapped[int | None] = mapped_column(Integer)
    total_floors: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="RUB")
    photos: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    phone: Mapped[str | None] = mapped_column(String(32), comment="Seller phone (parsed from source)")

    extra_fields: Mapped[dict | None] = mapped_column(
        JSONB, server_default="{}",
        comment="Platform-specific fields (balcony, renovation, etc.)",
    )

    # --- status / lifecycle ---
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="listing_status"),
        nullable=False,
        server_default=ListingStatus.ACTIVE.value,
        index=True,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- full-text search ---
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        comment="Auto-maintained via trigger: tsvector_update_trigger",
    )

    # --- timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # --- relationships ---
    favorites: Mapped[list[Favorite]] = relationship(back_populates="listing", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_listings_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_listings_city_status_price", "city", "status", "price"),
        Index("ix_listings_deactivated_at", "deactivated_at", postgresql_where="status = 'inactive'"),
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    telegram_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    favorites: Mapped[list[Favorite]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="favorites")
    listing: Mapped[Listing] = relationship(back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_listing_favorite"),
    )


# ---------------------------------------------------------------------------
# Subscriptions (saved search alerts)
# ---------------------------------------------------------------------------

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    channel: Mapped[SubscriptionChannel] = mapped_column(
        Enum(SubscriptionChannel, name="sub_channel"), nullable=False,
    )

    # --- filter criteria (stored as JSON for flexibility) ---
    filter_city: Mapped[str | None] = mapped_column(String(128))
    filter_rooms_min: Mapped[int | None] = mapped_column(Integer)
    filter_rooms_max: Mapped[int | None] = mapped_column(Integer)
    filter_price_min: Mapped[int | None] = mapped_column(Integer)
    filter_price_max: Mapped[int | None] = mapped_column(Integer)
    filter_area_min: Mapped[float | None] = mapped_column(Float)
    filter_area_max: Mapped[float | None] = mapped_column(Float)
    filter_sources: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="subscriptions")
