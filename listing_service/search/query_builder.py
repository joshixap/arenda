"""Chainable query builder for listing search.

Adding a new filter:
  1. Create a new FilterBase subclass with apply()
  2. Pass it into ListingQueryBuilder.filters — done.
  No existing code needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.dialects.postgresql import array

# Avoid circular import at type-check time; at runtime the model is available.
from shared.models import Listing


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------

class SortField(str, Enum):
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    DATE_ASC = "date_asc"
    DATE_DESC = "date_desc"
    AREA_ASC = "area_asc"
    AREA_DESC = "area_desc"


_SORT_MAP = {
    SortField.PRICE_ASC: asc(Listing.price),
    SortField.PRICE_DESC: desc(Listing.price),
    SortField.DATE_ASC: asc(Listing.created_at),
    SortField.DATE_DESC: desc(Listing.created_at),
    SortField.AREA_ASC: asc(Listing.area),
    SortField.AREA_DESC: desc(Listing.area),
}

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Filter base
# ---------------------------------------------------------------------------

class FilterBase(ABC):
    """Single responsibility: append one WHERE clause."""

    @abstractmethod
    def apply(self, query: Select) -> Select:
        ...


# ---------------------------------------------------------------------------
# Concrete filters
# ---------------------------------------------------------------------------

class CityFilter(FilterBase):
    def __init__(self, city: str):
        self.city = city.strip().lower()

    def apply(self, query: Select) -> Select:
        return query.where(func.lower(Listing.city) == self.city)


class RoomsFilter(FilterBase):
    def __init__(self, rooms_min: int | None = None, rooms_max: int | None = None):
        self.rooms_min = rooms_min
        self.rooms_max = rooms_max

    def apply(self, query: Select) -> Select:
        if self.rooms_min is not None:
            query = query.where(Listing.rooms >= self.rooms_min)
        if self.rooms_max is not None:
            query = query.where(Listing.rooms <= self.rooms_max)
        return query


class PriceFilter(FilterBase):
    def __init__(self, price_min: int | None = None, price_max: int | None = None):
        self.price_min = price_min
        self.price_max = price_max

    def apply(self, query: Select) -> Select:
        if self.price_min is not None:
            query = query.where(Listing.price >= self.price_min)
        if self.price_max is not None:
            query = query.where(Listing.price <= self.price_max)
        return query


class SourceFilter(FilterBase):
    """Filter listings that were seen on ANY of the given sources."""

    def __init__(self, sources: list[str]):
        self.sources = sources

    def apply(self, query: Select) -> Select:
        # seen_on && ARRAY['avito','cian']  — PostgreSQL array overlap
        return query.where(Listing.seen_on.overlap(self.sources))


class AreaFilter(FilterBase):
    def __init__(self, area_min: float | None = None, area_max: float | None = None):
        self.area_min = area_min
        self.area_max = area_max

    def apply(self, query: Select) -> Select:
        if self.area_min is not None:
            query = query.where(Listing.area >= self.area_min)
        if self.area_max is not None:
            query = query.where(Listing.area <= self.area_max)
        return query


class FullTextFilter(FilterBase):
    """PostgreSQL full-text search via pre-computed tsvector column."""

    def __init__(self, query_text: str):
        self.query_text = query_text

    def apply(self, query: Select) -> Select:
        ts_query = func.plainto_tsquery("russian", self.query_text)
        return query.where(Listing.search_vector.op("@@")(ts_query))


class StatusFilter(FilterBase):
    def __init__(self, status: str = "active"):
        self.status = status

    def apply(self, query: Select) -> Select:
        return query.where(Listing.status == self.status)


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

@dataclass
class PageParams:
    page: int = 1
    size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self):
        self.page = max(1, self.page)
        self.size = max(1, min(self.size, MAX_PAGE_SIZE))

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class ListingQueryBuilder:
    """Assembles a SELECT query from a list of independent filters.

    Usage:
        builder = ListingQueryBuilder(
            filters=[CityFilter("москва"), PriceFilter(price_max=50000)],
            sort=SortField.PRICE_ASC,
            page=PageParams(page=2, size=20),
        )
        stmt = builder.build()           # -> sqlalchemy.Select
        count_stmt = builder.build_count()  # -> SELECT count(*)
    """

    def __init__(
        self,
        filters: list[FilterBase] | None = None,
        sort: SortField = SortField.DATE_DESC,
        page: PageParams | None = None,
    ):
        self.filters = filters or []
        self.sort = sort
        self.page = page or PageParams()

    def _base_query(self) -> Select:
        query = select(Listing)
        for f in self.filters:
            query = f.apply(query)
        return query

    def build(self) -> Select:
        query = self._base_query()
        query = query.order_by(_SORT_MAP[self.sort])
        query = query.offset(self.page.offset).limit(self.page.size)
        return query

    def build_count(self) -> Select:
        query = select(func.count()).select_from(Listing)
        for f in self.filters:
            query = f.apply(query)
        return query
