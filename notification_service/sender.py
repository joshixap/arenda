"""Notification senders — Telegram."""
from __future__ import annotations

import logging

import aiohttp

from shared.config import settings
from shared.events import ListingNewEvent
from shared.models import Subscription, User

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/sendMessage"


def _format_message(event: ListingNewEvent, sub: Subscription) -> str:
    rooms = f"{event.rooms}-комн." if event.rooms else "Студия"
    area = f", {event.area} м²" if event.area else ""
    return (
        f"🏠 *Новое объявление по подписке «{sub.name}»*\n\n"
        f"{rooms}{area} — {event.price:,} ₽/мес.\n"
        f"📍 {event.city}\n"
        f"📌 {event.title}\n"
        f"🔗 [Открыть объявление]({event.source_url})\n"
        f"_Источник: {event.source}_"
    )


async def send_telegram(
    http: aiohttp.ClientSession,
    user: User,
    sub: Subscription,
    event: ListingNewEvent,
) -> None:
    if not user.telegram_id or not settings.telegram_bot_token:
        logger.debug("telegram: skip user %s — no telegram_id or token not set", user.id)
        return

    text = _format_message(event, sub)
    url = _TG_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": user.telegram_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    try:
        async with http.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.warning("telegram: send failed status=%s body=%s", resp.status, body[:200])
    except Exception as exc:
        logger.exception("telegram: send error for user %s: %s", user.id, exc)
