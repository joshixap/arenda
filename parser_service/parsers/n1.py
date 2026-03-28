"""N1.ru parser stub."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from parser_service.parsers.base import BaseParser, RawListing

logger = logging.getLogger(__name__)


class N1Parser(BaseParser):
    source_name = "n1"

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        # TODO: implement n1.ru API parsing
        # Endpoint: https://api.n1.ru/api/v1/offers/
        logger.info("n1: parser not yet implemented")
        return
        yield
