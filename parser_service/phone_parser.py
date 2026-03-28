"""Avito phone number parser.

Два подхода объединены в один модуль:

1. Mobile API (основной) — из gist DxDiagDx/8043c081e7e28c8d3f43200dbb93f57d:
   GET https://m.avito.ru/api/1/items/{offer_id}/phone?key=af0deccbgcgidddjgnvljitntccdduijhdinfgjgfjir
   Возвращает tel:-URI, из которого извлекается номер.

2. spfa.ru batch API (запасной) — из Duff89/parser_avito: utils/parse_phone.py:
   POST https://spfa.ru/api/phone/ с batch ID-шников (по 10 штук).
   Требует отдельный API-ключ в конфиге.

Использование:
    phone_parser = AvitoPhoneParser(proxy="http://...", spfa_api_key="...")
    phone = await phone_parser.get_phone("2504159999")

    # Пакетная обработка (как в Duff89)
    phones = await phone_parser.get_phones_batch(["123", "456", "789"])
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Sequence

import aiohttp

logger = logging.getLogger(__name__)

# Публичный ключ из gist DxDiagDx — работает без авторизации
_AVITO_MOBILE_API_KEY = "af0deccbgcgidddjgnvljitntccdduijhdinfgjgfjir"
_MOBILE_API_URL = "https://m.avito.ru/api/1/items/{offer_id}/phone"

# spfa.ru API (Duff89) — требует ключ из конфига
_SPFA_API_URL = "https://spfa.ru/api/phone/"
_SPFA_BATCH_SIZE = 10   # Duff89 использует батчи по 10

_PHONE_RE = re.compile(r"[\d\-\(\)\+\s]{7,}")


class AvitoPhoneParser:
    """Асинхронный парсер телефонов Avito.

    Args:
        session: Готовая aiohttp.ClientSession (шарится с остальными воркерами).
        proxy: HTTP-прокси строка, например "http://user:pass@host:port".
        spfa_api_key: API-ключ spfa.ru для batch-режима (опционально).
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy: str | None = None,
        spfa_api_key: str | None = None,
    ):
        self._session = session
        self._proxy = proxy
        self._spfa_api_key = spfa_api_key

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_phone(self, offer_id: str | int) -> str | None:
        """Получить телефон для одного объявления.

        Сначала пробует mobile API (gist DxDiagDx), при ошибке — spfa.ru.
        """
        phone = await self._mobile_api(str(offer_id))
        if phone:
            return phone

        if self._spfa_api_key:
            phones = await self._spfa_batch([str(offer_id)])
            return phones.get(str(offer_id))

        return None

    async def get_phones_batch(self, offer_ids: Sequence[str | int]) -> dict[str, str]:
        """Получить телефоны для нескольких объявлений.

        Если есть spfa_api_key — использует batch API (эффективнее).
        Иначе — параллельные mobile API запросы.

        Returns:
            dict: {offer_id: phone_number} только для успешно найденных.
        """
        ids = [str(i) for i in offer_ids]

        if self._spfa_api_key:
            return await self._spfa_batch(ids)

        import asyncio
        results = await asyncio.gather(
            *[self._mobile_api(offer_id) for offer_id in ids],
            return_exceptions=True,
        )
        return {
            offer_id: phone
            for offer_id, phone in zip(ids, results)
            if isinstance(phone, str) and phone
        }

    # ------------------------------------------------------------------
    # Mobile API (gist DxDiagDx) — основной метод
    # ------------------------------------------------------------------

    async def _mobile_api(self, offer_id: str) -> str | None:
        """
        Источник: https://gist.github.com/DxDiagDx/8043c081e7e28c8d3f43200dbb93f57d

        GET https://m.avito.ru/api/1/items/{offer_id}/phone?key=af0dec...
        Ответ: {"status": "ok", "result": {"action": {"uri": "tel:+7...?number=+7..."}}}
        Телефон в query-параметре number= внутри tel:-URI.
        """
        url = _MOBILE_API_URL.format(offer_id=offer_id)
        params = {"key": _AVITO_MOBILE_API_KEY}
        try:
            async with self._session.get(
                url,
                params=params,
                proxy=self._proxy,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 404:
                    return None
                if resp.status != 200:
                    logger.debug("avito phone mobile API: status %d for id=%s", resp.status, offer_id)
                    return None

                data = await resp.json()

                if data.get("status") != "ok":
                    msg = data.get("result", {}).get("message", "unknown error")
                    logger.debug("avito phone: %s for id=%s", msg, offer_id)
                    return None

                uri = data.get("result", {}).get("action", {}).get("uri", "")
                return self._extract_phone_from_uri(uri)

        except Exception as exc:
            logger.debug("avito phone mobile API error id=%s: %s", offer_id, exc)
            return None

    @staticmethod
    def _extract_phone_from_uri(uri: str) -> str | None:
        """
        tel:+79001234567?number=%2B79001234567  →  +79001234567

        Логика из gist:
          phone = urllib.parse.unquote(uri.split('number=')[1])
        """
        if not uri:
            return None
        try:
            if "number=" in uri:
                raw = uri.split("number=")[1]
                phone = urllib.parse.unquote(raw)
                # Убираем лишние параметры если есть
                phone = phone.split("&")[0].strip()
                return _clean_phone(phone)
            # Fallback: просто из tel: части
            if uri.startswith("tel:"):
                return _clean_phone(uri[4:].split("?")[0])
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # spfa.ru batch API (Duff89) — запасной метод
    # ------------------------------------------------------------------

    async def _spfa_batch(self, offer_ids: list[str]) -> dict[str, str]:
        """
        Источник: Duff89/parser_avito — utils/parse_phone.py: ParsePhone.parse_phone()

        POST https://spfa.ru/api/phone/
        Body: {"ids": ["id1", "id2", ...], "api_key": "..."}
        Батчи по _SPFA_BATCH_SIZE (10) — как в оригинале.

        Returns:
            dict: {offer_id: cleaned_phone}
        """
        result: dict[str, str] = {}

        for i in range(0, len(offer_ids), _SPFA_BATCH_SIZE):
            batch = offer_ids[i: i + _SPFA_BATCH_SIZE]
            try:
                async with self._session.post(
                    _SPFA_API_URL,
                    json={"ids": batch, "api_key": self._spfa_api_key},
                    proxy=self._proxy,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        logger.warning("spfa phone API: status %d for batch %s", resp.status, batch)
                        continue
                    data = await resp.json()

                    # spfa.ru возвращает {offer_id: phone_or_null}
                    for offer_id, phone in data.items():
                        if phone:
                            cleaned = _clean_phone(str(phone))
                            if cleaned:
                                result[offer_id] = cleaned

            except Exception as exc:
                logger.error("spfa phone API error batch=%s: %s", batch, exc)

        return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _clean_phone(raw: str) -> str | None:
    """Нормализует номер: убирает пробелы, скобки, дефисы, проверяет длину."""
    if not raw:
        return None
    digits_only = re.sub(r"[^\d+]", "", raw)
    # Российский номер: 11 цифр (или +7 + 10)
    if len(digits_only) >= 10:
        return digits_only
    return None
