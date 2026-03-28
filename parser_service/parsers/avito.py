"""Avito.ru parser.

Реализация основана на подходе из Duff89/parser_avito:
  - curl_cffi с имперсонацией Chrome для обхода Cloudflare/anti-bot
  - Извлечение данных из <script type="mime/invalid" data-mfe-state="true">
  - Пагинация через next-page URL из JSON

Парсинг телефона — отдельный модуль parser_service/phone_parser.py
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
import time
from typing import AsyncIterator

from bs4 import BeautifulSoup

from parser_service.parsers.base import BaseParser, RawListing

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
except ImportError:  # pragma: no cover
    CurlAsyncSession = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Имперсонируем Chrome 124 — тот же UA, что использует Duff89
_IMPERSONATE = "chrome124"

_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "ru-RU,ru;q=0.9",
    "accept-encoding": "gzip, deflate, br",
}


class AvitoParser(BaseParser):
    source_name = "avito"

    def __init__(
        self,
        http_session=None,               # не используется — создаём свою curl_cffi сессию
        search_url: str = "https://www.avito.ru/sankt-peterburg/kvartiry/sdam/na_dlitelnyy_srok",
        max_pages: int = 5,
        proxy: str | None = None,
    ):
        super().__init__(http_session)
        self.search_url = search_url
        self.max_pages = max_pages
        self.proxy = proxy

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        if CurlAsyncSession is None:
            logger.error("avito: curl_cffi not installed — run: pip install curl_cffi")
            return
        async with CurlAsyncSession(impersonate=_IMPERSONATE) as session:
            url = self.search_url
            for page_num in range(1, self.max_pages + 1):
                page_url = self._add_page(url, page_num)
                data = await self._fetch_page_json(session, page_url)
                if not data:
                    logger.warning("avito: no data on page %d, stopping", page_num)
                    break

                items = (
                    data.get("catalog", {}).get("items")
                    or data.get("items")
                    or []
                )
                if not items:
                    logger.info("avito: no items on page %d", page_num)
                    break

                for item in items:
                    raw = self._parse_item(item)
                    if raw:
                        yield raw

                logger.info("avito: page %d — got %d items", page_num, len(items))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_page_json(self, session, url: str) -> dict | None:
        """Загружает страницу и извлекает JSON из <script type='mime/invalid'>."""
        try:
            resp = await session.get(
                url,
                headers=_HEADERS,
                proxies={"https": self.proxy, "http": self.proxy} if self.proxy else None,
                timeout=20,
            )
        except Exception as exc:
            logger.error("avito: HTTP error %s: %s", url, exc)
            return None

        if resp.status_code == 429:
            logger.warning("avito: rate limited (429)")
            return None
        if resp.status_code != 200:
            logger.error("avito: unexpected status %d", resp.status_code)
            return None

        return self._find_json_on_page(resp.text)

    @staticmethod
    def _find_json_on_page(html_code: str) -> dict:
        """
        Извлекает JSON-данные из <script type="mime/invalid" data-mfe-state="true">.
        Логика взята из Duff89/parser_avito: parser_cls.py -> find_json_on_page()
        """
        soup = BeautifulSoup(html_code, "html.parser")
        try:
            for script in soup.select("script"):
                if (
                    script.get("type") == "mime/invalid"
                    and script.get("data-mfe-state") == "true"
                    and "sandbox" not in script.text
                ):
                    text = script.text.strip()
                    if not text:
                        continue
                    data = json.loads(html_lib.unescape(text))
                    # Проверяем что это страница с листингами, а не другие MFE-блоки
                    if data.get("i18n", {}).get("hasMessages", {}):
                        return data.get("state", {}).get("data", {})
        except Exception as exc:
            logger.error("avito: JSON extraction error: %s", exc)
        return {}

    def _parse_item(self, item: dict) -> RawListing | None:
        """Нормализует один элемент из JSON каталога Avito."""
        try:
            # Цена
            price_info = item.get("priceDetailed") or item.get("price") or {}
            price = self._extract_price(price_info)
            if not price:
                return None

            # Адрес и геолокация
            geo = item.get("geo") or {}
            coords = geo.get("coordinates") or {}
            address_parts = [
                geo.get("formattedAddress") or "",
                geo.get("address") or "",
                (item.get("location") or {}).get("name") or "",
            ]
            address = next((a for a in address_parts if a), "")

            # Параметры квартиры (из IVA-компонент)
            params = self._extract_iva_params(item)

            title = item.get("title") or ""

            return self.make_raw(
                source_id=str(item["id"]),
                source_url="https://www.avito.ru" + (item.get("urlPath") or item.get("url") or ""),
                title=title,
                city=self._extract_city(item),
                address=address,
                price=price,
                rooms=self._extract_rooms(title, params),
                area=self._extract_area(title, params),
                floor=params.get("floor"),
                total_floors=params.get("total_floors"),
                latitude=coords.get("lat"),
                longitude=coords.get("lng") or coords.get("lon"),
                description=item.get("description"),
                photos=self._extract_photos(item),
                extra_fields={
                    "avito_id": item["id"],
                    "seller_id": item.get("sellerId"),
                    "is_promotion": item.get("isPromotion", False),
                },
            )
        except Exception as exc:
            logger.debug("avito: item parse error id=%s: %s", item.get("id"), exc)
            return None

    # ------------------------------------------------------------------
    # Field extractors
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_price(price_info: dict) -> int | None:
        for key in ("value", "price", "valueText"):
            val = price_info.get(key)
            if val:
                try:
                    cleaned = re.sub(r"[^\d]", "", str(val))
                    if cleaned:
                        return int(cleaned)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _extract_city(item: dict) -> str:
        location = item.get("location") or {}
        return location.get("name") or "Санкт-Петербург"

    @staticmethod
    def _extract_iva_params(item: dict) -> dict:
        """Извлекает параметры из IVA-компонент (структура из Avito MFE JSON)."""
        result: dict = {}
        iva_list = item.get("iva") or []
        for component in iva_list:
            content = component.get("content") or []
            for block in content:
                text = block.get("value") or block.get("text") or ""
                # Этаж: "3/9 эт."
                floor_match = re.search(r"(\d+)/(\d+)\s*эт", text)
                if floor_match:
                    result["floor"] = int(floor_match.group(1))
                    result["total_floors"] = int(floor_match.group(2))
                # Площадь: "52,5 м²"
                area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*м²", text)
                if area_match:
                    result["area"] = float(area_match.group(1).replace(",", "."))
        return result

    @staticmethod
    def _extract_rooms(title: str, params: dict) -> int | None:
        title_lower = title.lower()
        if any(w in title_lower for w in ("студия", "studio")):
            return 0
        m = re.search(r"(\d+)-комн", title_lower)
        if m:
            return int(m.group(1))
        return params.get("rooms")

    @staticmethod
    def _extract_area(title: str, params: dict) -> float | None:
        if "area" in params:
            return params["area"]
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*м²", title)
        if m:
            return float(m.group(1).replace(",", "."))
        return None

    @staticmethod
    def _extract_photos(item: dict) -> list[str]:
        images = item.get("images") or item.get("gallery", {}).get("images") or []
        result = []
        for img in images[:10]:
            if isinstance(img, dict):
                url = img.get("1280x960") or img.get("640x480") or img.get("url") or ""
                if url:
                    result.append(url)
        return result

    @staticmethod
    def _add_page(url: str, page: int) -> str:
        if page == 1:
            return url
        if "?" in url:
            return f"{url}&p={page}"
        return f"{url}?p={page}"
