"""Daily push scheduler — runs hourly, sends to users whose local time hits PUSH_DAILY_HOUR."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, key_horoscope
from core.logging import get_logger
from core.settings import settings
from db.database import AsyncSessionLocal
from db.models import NotificationLog, NotificationStatus, NotificationType, User
from services.notifications.push import (
    DAILY_OPEN_APP_LABEL,
    build_daily_message,
    build_open_app_markup,
    send_message,
)

log = get_logger(__name__)

_SIGN_RU: dict[str, str] = {
    "aries": "Овен", "taurus": "Телец", "gemini": "Близнецы",
    "cancer": "Рак", "leo": "Лев", "virgo": "Дева",
    "libra": "Весы", "scorpio": "Скорпион", "sagittarius": "Стрелец",
    "capricorn": "Козерог", "aquarius": "Водолей", "pisces": "Рыбы",
}


async def _already_sent_today(db: AsyncSession, user_id: int) -> bool:
    today = date.today()
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == user_id,
            NotificationLog.type == NotificationType.DAILY_HOROSCOPE,
            NotificationLog.status == NotificationStatus.SENT,
            NotificationLog.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=UTC),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def send_daily_pushes() -> None:
    """Hourly job: find users whose local hour == PUSH_DAILY_HOUR and send them today's horoscope."""
    target_hour = settings.PUSH_DAILY_HOUR
    now_utc = datetime.now(UTC)
    today_iso = date.today().isoformat()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.push_enabled.is_(True), User.sun_sign.is_not(None))
        )
        users: list[User] = list(result.scalars().all())

        sent = 0
        skipped = 0
        failed = 0
        for user in users:
            tz_name = user.birth_tz or "UTC"
            try:
                local_now = now_utc.astimezone(ZoneInfo(tz_name))
            except Exception:
                local_now = now_utc
            if local_now.hour != target_hour:
                continue

            if await _already_sent_today(db, user.id):
                skipped += 1
                continue

            if user.sun_sign is None:
                skipped += 1
                continue

            sign = user.sun_sign.value
            cached = await cache_get(key_horoscope(sign, today_iso, "today"))
            if not cached:
                skipped += 1
                db.add(NotificationLog(
                    user_id=user.id,
                    type=NotificationType.DAILY_HOROSCOPE,
                    status=NotificationStatus.SKIPPED,
                    error="no cached horoscope",
                ))
                continue

            text = build_daily_message(
                user,
                sign_ru=_SIGN_RU.get(sign, sign),
                text_ru=cached.get("text_ru", ""),
                energy=cached.get("energy", {}),
            )
            ok = await send_message(
                db,
                user,
                text,
                type_=NotificationType.DAILY_HOROSCOPE,
                reply_markup=build_open_app_markup(DAILY_OPEN_APP_LABEL),
            )
            if ok:
                sent += 1
            else:
                failed += 1

        await db.commit()
        log.info("scheduler.daily_push_done", sent=sent, skipped=skipped, failed=failed)
