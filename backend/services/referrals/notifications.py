"""Telegram-side notification when a referrer earns Premium days.

In Model B the referrer only wins when their friend actually pays. Since
that can happen days after the friend joined, we have to *push* the news
back to the referrer — otherwise the programme feels broken.

Best-effort: a failed sendMessage call must not roll back the database
bonus grant.
"""

from __future__ import annotations

import httpx

from core.logging import get_logger
from core.settings import settings

log = get_logger(__name__)


async def notify_referrer_of_bonus(
    referrer_id: int,
    referee_name: str,
    days: int,
) -> None:
    """Send a Telegram message about earned Premium days. Swallows errors."""
    text = (
        f"✦ <b>Премиум продлён!</b>\n\n"
        f"Ваш друг {referee_name} сделал первую покупку.\n"
        f"Вам начислено <b>+{days} дней Premium</b>.\n\n"
        f"Откройте бота и посмотрите статус →"
    )
    reply_markup: dict | None = None
    if settings.MINIAPP_URL:
        reply_markup = {
            "inline_keyboard": [[
                {"text": "Открыть приложение",
                 "web_app": {"url": settings.MINIAPP_URL}},
            ]]
        }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": referrer_id,
                    "text": text,
                    "parse_mode": "HTML",
                    **({"reply_markup": reply_markup} if reply_markup else {}),
                },
            )
        data = resp.json()
        if not data.get("ok"):
            log.warning(
                "referral.notify_failed",
                referrer_id=referrer_id,
                response=data,
            )
        else:
            log.info("referral.notify_sent", referrer_id=referrer_id, days=days)
    except Exception as e:  # noqa: BLE001
        log.error(
            "referral.notify_exception",
            referrer_id=referrer_id,
            error=str(e),
        )
