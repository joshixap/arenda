"""Cian.ru parser — uses Cian's public search API."""
from __future__ import annotations

import logging
from typing import AsyncIterator

import aiohttp

from parser_service.parsers.base import BaseParser, RawListing

logger = logging.getLogger(__name__)

_API_URL = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120",
    "Content-Type": "application/json",
}


class CianParser(BaseParser):
    source_name = "cian"

    def __init__(self, http_session: aiohttp.ClientSession | None = None, region_id: int = 2):
        super().__init__(http_session)
        self.region_id = region_id  # 2 = SPb, 1 = Moscow

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        page = 1
        while True:
            payload = {
                "jsonQuery": {
                    "_type": "flatrent",
                    "region": {"type": "terms", "value": [self.region_id]},
                    "page": {"type": "term", "value": page},
                    "room": {"type": "terms", "value": [1, 2, 3, 4, 5]},
                }
            }
            try:
                async with self.http.post(_API_URL, json=payload, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status in (403, 429):
                        logger.warning("cian: blocked (status %s), skipping", resp.status)
                        break
                    if resp.status != 200:
                        logger.error("cian: status %s", resp.status)
                        break
                    data = await resp.json(content_type=None)
                    if "offersSerialized" not in str(data.get("data", {})):
                        logger.warning("cian: unexpected response (captcha?)")
                        break
            except Exception as exc:
                logger.exception("cian: fetch error page %s: %s", page, exc)
                break

            offers = data.get("data", {}).get("offersSerialized", [])
            if not offers:
                break

            for offer in offers:
                raw = self._parse_offer(offer)
                if raw:
                    yield raw

            if len(offers) < 28:
                break
            page += 1

    def _parse_offer(self, offer: dict) -> RawListing | None:
        try:
            price = int(offer.get("bargainTerms", {}).get("priceRur", 0))
            if price <= 0:
                return None

            geo = offer.get("geo", {})
            address_parts = [obj.get("name", "") for obj in geo.get("address", [])]
            address = ", ".join(p for p in address_parts if p)
            coords = geo.get("coordinates", {})
            building = offer.get("building", {})

            return self.make_raw(
                source_id=str(offer["id"]),
                source_url=offer.get("fullUrl", f"https://cian.ru/rent/flat/{offer['id']}/"),
                title=offer.get("title") or f"{offer.get('roomsCount', '?')}-комн. квартира",
                city="Санкт-Петербург" if self.region_id == 2 else "Москва",
                address=address,
                price=price,
                rooms=offer.get("roomsCount"),
                area=offer.get("totalArea"),
                floor=offer.get("floorNumber"),
                total_floors=building.get("floorsCount"),
                latitude=coords.get("lat"),
                longitude=coords.get("lng"),
                description=offer.get("description"),
                photos=[p.get("fullUrl", "") for p in offer.get("photos", [])[:10]],
                extra_fields={"cian_id": offer["id"]},
            )
        except Exception as exc:
            logger.debug("cian: skip offer: %s", exc)
            return None
