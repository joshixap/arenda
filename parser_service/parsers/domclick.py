"""Domclick.ru parser stub."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from parser_service.parsers.base import BaseParser, RawListing

logger = logging.getLogger(__name__)


class DomclickParser(BaseParser):
    source_name = "domclick"

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        # TODO: implement Domclick API parsing
        # Endpoint: https://api.domclick.ru/catalog/offer/v4/search
        logger.info("domclick: parser not yet implemented")
        return
        yield  # make it an async generator
