"""Move.ru parser stub."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from parser_service.parsers.base import BaseParser, RawListing

logger = logging.getLogger(__name__)


class MoveParser(BaseParser):
    source_name = "move"

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        # TODO: implement move.ru API parsing
        # Endpoint: https://www.move.ru/api/
        logger.info("move: parser not yet implemented")
        return
        yield
