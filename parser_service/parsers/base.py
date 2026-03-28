"""Abstract base for all rental platform parsers.

Adding a new source:
  1. Create parser_service/parsers/<source>.py
  2. Subclass BaseParser, set source_name, implement fetch_listings()
  3. Register in PARSER_REGISTRY (auto-discovered on import)
  No existing code needs to change.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

# ---------------------------------------------------------------------------
# Raw listing — everything a parser can extract before normalisation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RawListing:
    source: str
    source_id: str
    source_url: str
    title: str
    city: str
    address: str
    price: int
    currency: str = "RUB"
    rooms: int | None = None
    area: float | None = None
    floor: int | None = None
    total_floors: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    photos: list[str] = field(default_factory=list)
    extra_fields: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parser registry — parsers self-register on class creation
# ---------------------------------------------------------------------------

PARSER_REGISTRY: dict[str, type[BaseParser]] = {}


class _ParserMeta(type(ABC)):
    """Metaclass that auto-registers concrete parser subclasses."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(cls, name, bases, namespace, **kwargs):
        super().__init__(name, bases, namespace, **kwargs)
        # Only register concrete parsers (those with source_name set directly)
        if "source_name" in namespace and namespace["source_name"] is not None:
            PARSER_REGISTRY[namespace["source_name"]] = cls


# ---------------------------------------------------------------------------
# Base parser
# ---------------------------------------------------------------------------


class BaseParser(ABC, metaclass=_ParserMeta):
    """Abstract parser. Subclass per source, implement fetch_listings()."""

    source_name: str = None  # override in subclass, e.g. "avito"

    def __init__(self, http_session=None):
        """
        Args:
            http_session: aiohttp.ClientSession or httpx.AsyncClient.
                          Injected by the scheduler so parsers share a pool.
        """
        self.http = http_session

    # ---- deduplication hash ------------------------------------------------

    @staticmethod
    def compute_dedup_hash(address: str, area: float | None, price: int) -> str:
        """Deterministic hash: sha256(normalised_address | area | price).

        Normalisation: lowercase, strip whitespace, collapse spaces.
        area is rounded to 1 decimal to absorb trivial discrepancies.
        """
        norm_address = " ".join(address.lower().split())
        area_str = f"{area:.1f}" if area is not None else "none"
        raw = f"{norm_address}|{area_str}|{price}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ---- abstract interface ------------------------------------------------

    @abstractmethod
    async def fetch_listings(self) -> AsyncIterator[RawListing]:
        """Yield parsed listings from the source.

        Implementation must:
          - Handle pagination internally
          - Yield RawListing objects one at a time (memory-friendly)
          - Raise on fatal errors, log and skip on per-listing errors
        """
        yield  # pragma: no cover  — makes the type checker happy
        ...

    # ---- convenience -------------------------------------------------------

    def make_raw(self, **kwargs) -> RawListing:
        """Create RawListing with source pre-filled."""
        return RawListing(source=self.source_name, **kwargs)
