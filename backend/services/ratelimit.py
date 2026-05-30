"""
Monthly per-user rate limits for expensive LLM-backed endpoints.

A "grinder" power-user with no caps can wipe out the Premium margin
on tarot / synastry / transit deep-dives (see UNIT_ECONOMICS.md). We
enforce a soft monthly ceiling per (user_id, endpoint_key) stored as
a Redis INCR counter that expires at the start of next month.

Usage:
    from services.ratelimit import enforce_monthly_limit
    await enforce_monthly_limit(user_id, "tarot_draw", limit=20)

Raises HTTPException(429) with a Russian message + the reset date.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException, status

from core.cache import get_redis
from core.logging import get_logger

log = get_logger(__name__)


_MONTHS_RU_GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _month_bucket() -> tuple[str, int]:
    """
    Return (`YYYY-MM` bucket key, seconds remaining in month) for the
    current UTC clock. The TTL only needs to cover until the bucket
    rolls over — we don't need exact end-of-month precision.
    """
    now = datetime.now(UTC)
    bucket = f"{now.year:04d}-{now.month:02d}"
    # Naïve "days left in month" → 31 caps it safely.
    if now.month == 12:
        next_month_first = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month_first = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    seconds_left = max(60, int((next_month_first - now).total_seconds()) + 60)
    return bucket, seconds_left


def _next_month_human() -> str:
    """`1 июля` — humane reset hint shown to the user."""
    now = datetime.now(UTC)
    if now.month == 12:
        nm = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        nm = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return f"{nm.day} {_MONTHS_RU_GENITIVE[nm.month - 1]}"


async def get_monthly_usage(user_id: int, key: str) -> int:
    """Read current month's counter (0 if absent). No mutation."""
    redis = get_redis()
    bucket, _ = _month_bucket()
    raw = await cast(object, redis.get(f"rl:{key}:{user_id}:{bucket}"))
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


async def enforce_monthly_limit(
    user_id: int,
    key: str,
    limit: int,
    *,
    feature_ru: str,
) -> None:
    """
    Increment the (user_id, key, month) counter and raise 429 if the
    new value exceeds `limit`. The counter is incremented BEFORE the
    work is done — on overflow we roll it back so a denied request
    doesn't burn through a slot.
    """
    if limit <= 0:
        return  # unlimited — short-circuit

    redis = get_redis()
    bucket, ttl = _month_bucket()
    redis_key = f"rl:{key}:{user_id}:{bucket}"

    # Atomic increment — Redis pipeline so we don't race
    pipe = redis.pipeline()
    pipe.incr(redis_key)
    pipe.expire(redis_key, ttl)
    results = await cast(object, pipe.execute())
    used = int(results[0]) if results else 0

    if used > limit:
        # Roll back our increment so the user doesn't lose a slot for
        # a request we're about to deny anyway.
        try:
            await cast(object, redis.decr(redis_key))
        except Exception:  # noqa: BLE001
            pass
        log.info(
            "ratelimit.exceeded",
            user_id=user_id, key=key, limit=limit, used=used,
        )
        reset = _next_month_human()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Лимит на {feature_ru} в этом месяце исчерпан "
                f"({limit} из {limit}). Обновится {reset}."
            ),
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": reset,
            },
        )


# Per-endpoint limits — single source of truth so we don't scatter
# magic numbers across route files. Adjust here if the unit economics
# changes.
LIMITS = {
    "tarot_draw": 20,         # any spread (3-card, celtic, week, relationship)
    "tarot_interpret": 20,    # piggyback on the draw cap; one per reading
    "synastry_calc": 5,       # both manual and request-accept variants
    "transit_details": 30,    # deep-dive LLM advice per aspect
}
