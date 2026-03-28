"""Yandex Realty parser stub."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from parser_service.parsers.base import BaseParser, RawListing

logger = logging.getLogger(__name__)


class YandexParser(BaseParser):
    source_name = "yandex"

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        # TODO: implement realty.yandex.ru API parsing
        # Endpoint: https://realty.yandex.ru/gate/react-page/get/
        logger.info("yandex: parser not yet implemented")
        return
        yield
