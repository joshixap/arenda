"""Unit tests for subscription matcher (no DB needed)."""
import uuid
from datetime import datetime

import pytest

from notification_service.matcher import _matches
from shared.events import ListingNewEvent
from shared.models import Subscription, SubscriptionChannel


def make_event(**kwargs) -> ListingNewEvent:
    defaults = dict(
        listing_id=uuid.uuid4(),
        source="avito",
        title="2-комн. квартира",
        city="Санкт-Петербург",
        price=45000,
        rooms=2,
        area=55.0,
        source_url="https://avito.ru/1",
        timestamp=datetime.utcnow(),
    )
    return ListingNewEvent(**{**defaults, **kwargs})


def make_sub(**kwargs) -> Subscription:
    sub = Subscription()
    sub.id = uuid.uuid4()
    sub.user_id = uuid.uuid4()
    sub.name = "test"
    sub.channel = SubscriptionChannel.TELEGRAM
    sub.is_active = True
    sub.filter_city = None
    sub.filter_rooms_min = None
    sub.filter_rooms_max = None
    sub.filter_price_min = None
    sub.filter_price_max = None
    sub.filter_area_min = None
    sub.filter_area_max = None
    sub.filter_sources = None
    for k, v in kwargs.items():
        setattr(sub, k, v)
    return sub


def test_no_filters_matches_all():
    assert _matches(make_event(), make_sub()) is True


def test_city_match():
    assert _matches(make_event(city="Москва"), make_sub(filter_city="Москва")) is True


def test_city_no_match():
    assert _matches(make_event(city="Москва"), make_sub(filter_city="Казань")) is False


def test_price_max_match():
    assert _matches(make_event(price=40000), make_sub(filter_price_max=50000)) is True


def test_price_max_no_match():
    assert _matches(make_event(price=70000), make_sub(filter_price_max=50000)) is False


def test_rooms_range_match():
    assert _matches(make_event(rooms=2), make_sub(filter_rooms_min=1, filter_rooms_max=3)) is True


def test_rooms_range_no_match():
    assert _matches(make_event(rooms=4), make_sub(filter_rooms_min=1, filter_rooms_max=3)) is False


def test_source_filter_match():
    assert _matches(make_event(source="avito"), make_sub(filter_sources=["avito", "cian"])) is True


def test_source_filter_no_match():
    assert _matches(make_event(source="move"), make_sub(filter_sources=["avito", "cian"])) is False


def test_combined_filters():
    event = make_event(city="Санкт-Петербург", price=50000, rooms=2, area=55.0, source="cian")
    sub = make_sub(
        filter_city="Санкт-Петербург",
        filter_price_max=60000,
        filter_rooms_min=2,
        filter_sources=["cian", "avito"],
    )
    assert _matches(event, sub) is True
