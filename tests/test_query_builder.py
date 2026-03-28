"""Unit tests for ListingQueryBuilder — no DB needed, just checks SQL generation."""
import pytest
from sqlalchemy import String
from sqlalchemy.dialects import postgresql

from listing_service.search.query_builder import (
    AreaFilter,
    CityFilter,
    ListingQueryBuilder,
    PageParams,
    PriceFilter,
    RoomsFilter,
    SortField,
    SourceFilter,
    StatusFilter,
)


def compile_query(builder: ListingQueryBuilder) -> str:
    stmt = builder.build()
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_no_filters_returns_all_active():
    builder = ListingQueryBuilder(filters=[StatusFilter("active")])
    sql = compile_query(builder)
    assert "ACTIVE" in sql or "active" in sql.lower()


def test_city_filter():
    builder = ListingQueryBuilder(filters=[CityFilter("москва")])
    sql = compile_query(builder)
    assert "москва" in sql.lower()


def test_price_filter():
    builder = ListingQueryBuilder(filters=[PriceFilter(price_min=20000, price_max=60000)])
    sql = compile_query(builder)
    assert "20000" in sql
    assert "60000" in sql


def test_rooms_filter():
    builder = ListingQueryBuilder(filters=[RoomsFilter(rooms_min=2, rooms_max=3)])
    sql = compile_query(builder)
    assert "2" in sql


def test_area_filter():
    builder = ListingQueryBuilder(filters=[AreaFilter(area_min=40.0)])
    sql = compile_query(builder)
    assert "40" in sql


def test_pagination():
    builder = ListingQueryBuilder(page=PageParams(page=3, size=10))
    sql = compile_query(builder)
    assert "LIMIT 10" in sql
    assert "OFFSET 20" in sql


def test_sort_price_asc():
    builder = ListingQueryBuilder(sort=SortField.PRICE_ASC)
    sql = compile_query(builder)
    assert "price ASC" in sql or "ASC" in sql


def test_count_query():
    builder = ListingQueryBuilder(filters=[CityFilter("спб"), PriceFilter(price_max=50000)])
    sql = str(builder.build_count().compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "count" in sql.lower()


def test_new_filter_doesnt_break_builder():
    """Adding a new filter class works without changing ListingQueryBuilder."""
    from listing_service.search.query_builder import FilterBase
    from shared.models import Listing

    class FloorFilter(FilterBase):
        def __init__(self, floor_min: int):
            self.floor_min = floor_min
        def apply(self, query):
            return query.where(Listing.floor >= self.floor_min)

    builder = ListingQueryBuilder(filters=[StatusFilter("active"), FloorFilter(3)])
    sql = compile_query(builder)
    assert "3" in sql
