"""Parser Service entry point — APScheduler + workers."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import all parsers to trigger PARSER_REGISTRY auto-registration
import parser_service.parsers.avito  # noqa: F401
import parser_service.parsers.cian  # noqa: F401
import parser_service.parsers.domclick  # noqa: F401
import parser_service.parsers.n1  # noqa: F401
import parser_service.parsers.yandex  # noqa: F401
import parser_service.parsers.youla  # noqa: F401
import parser_service.parsers.move  # noqa: F401

from parser_service.cleanup import run_cleanup
from parser_service.dedup import upsert_listing
from parser_service.parsers.base import PARSER_REGISTRY
from parser_service.phone_parser import AvitoPhoneParser
from parser_service.publisher import EventPublisher
from shared.config import settings
from shared.database import AsyncSessionLocal, engine
from shared.events import ListingDeactivatedEvent, ListingNewEvent
from shared.models import Base, Listing, ListingStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_parser(source_name: str, http_session: aiohttp.ClientSession, publisher: EventPublisher) -> None:
    parser_cls = PARSER_REGISTRY.get(source_name)
    if not parser_cls:
        logger.error("No parser registered for source: %s", source_name)
        return

    proxy = settings.parser_proxy or None
    parser = parser_cls(http_session=http_session, **({"proxy": proxy} if proxy and hasattr(parser_cls.__init__, "proxy") else {}))

    new_count = dup_count = err_count = 0
    new_avito_ids: list[tuple[str, str]] = []  # (listing_id, avito_source_id) для phone batch

    async with AsyncSessionLocal() as session:
        async for raw in parser.fetch_listings():
            try:
                listing_id, is_new = await upsert_listing(session, raw, source_name)
                if is_new:
                    new_count += 1
                    if source_name == "avito" and settings.parse_phones:
                        new_avito_ids.append((str(listing_id), raw.source_id))
                    event = ListingNewEvent(
                        listing_id=listing_id,
                        source=source_name,
                        title=raw.title,
                        city=raw.city,
                        price=raw.price,
                        rooms=raw.rooms,
                        area=raw.area,
                        source_url=raw.source_url,
                    )
                    await publisher.publish_new(event)
                else:
                    dup_count += 1
            except Exception as exc:
                err_count += 1
                logger.exception("%s: upsert error: %s", source_name, exc)

    # Batch phone parsing для Avito (только новых)
    if new_avito_ids and settings.parse_phones:
        await _fetch_and_save_phones(http_session, new_avito_ids)

    logger.info("%s: new=%d dupes=%d errors=%d", source_name, new_count, dup_count, err_count)


async def _fetch_and_save_phones(
    http_session: aiohttp.ClientSession,
    id_pairs: list[tuple[str, str]],  # [(listing_uuid, avito_source_id), ...]
) -> None:
    """Получает телефоны через AvitoPhoneParser и сохраняет в БД."""
    from sqlalchemy import update
    phone_parser = AvitoPhoneParser(
        session=http_session,
        proxy=settings.parser_proxy or None,
        spfa_api_key=settings.spfa_api_key or None,
    )
    avito_ids = [src_id for _, src_id in id_pairs]
    phones = await phone_parser.get_phones_batch(avito_ids)

    if not phones:
        return

    # Сохраняем телефоны в Listing
    async with AsyncSessionLocal() as session:
        for listing_uuid, avito_src_id in id_pairs:
            phone = phones.get(avito_src_id)
            if phone:
                await session.execute(
                    update(Listing).where(Listing.id == listing_uuid).values(phone=phone)
                )
        await session.commit()
    logger.info("phones: saved %d phone numbers", len(phones))


async def run_all_parsers(http_session: aiohttp.ClientSession, publisher: EventPublisher) -> None:
    tasks = [
        asyncio.create_task(run_parser(name, http_session, publisher))
        for name in PARSER_REGISTRY
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def run_daily_cleanup(publisher: EventPublisher) -> None:
    async with AsyncSessionLocal() as session:
        deleted = await run_cleanup(session, publisher)
    logger.info("cleanup: finished, deleted=%d", deleted)


async def main() -> None:
    # Init DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    publisher = EventPublisher(redis_client)

    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
    http_session = aiohttp.ClientSession(connector=connector)

    scheduler = AsyncIOScheduler()

    # Parser job — every N minutes
    scheduler.add_job(
        run_all_parsers,
        trigger="interval",
        minutes=settings.parser_interval_minutes,
        args=[http_session, publisher],
        id="parsers",
        max_instances=1,
        misfire_grace_time=60,
    )

    # Cleanup job — daily at 03:00
    scheduler.add_job(
        run_daily_cleanup,
        trigger="cron",
        hour=settings.cleanup_cron_hour,
        minute=0,
        args=[publisher],
        id="cleanup",
        max_instances=1,
    )

    scheduler.start()
    logger.info("Parser service started. Registered parsers: %s", list(PARSER_REGISTRY.keys()))

    # Run once immediately on startup
    asyncio.create_task(run_all_parsers(http_session, publisher))

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        await http_session.close()
        await redis_client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
