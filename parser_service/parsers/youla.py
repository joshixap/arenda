"""Youla.io parser stub."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from parser_service.parsers.base import BaseParser, RawListing

logger = logging.getLogger(__name__)


class YoulaParser(BaseParser):
    source_name = "youla"

    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        # TODO: implement youla.io API parsing
        # Endpoint: https://youla.io/web-api/graphql
        logger.info("youla: parser not yet implemented")
        return
        yield
