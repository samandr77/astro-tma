"""
Redis cache client — singleton pattern via lifespan.
All cache keys live here to avoid magic strings across the codebase.
"""
import json
from collections.abc import Awaitable
from typing import Any, cast

import redis.asyncio as aioredis

from core.logging import get_logger
from core.settings import settings

log = get_logger(__name__)

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    await cast(Awaitable[Any], _redis.ping())
    log.info("redis.connected", url=str(settings.REDIS_URL))


async def close_redis() -> None:
    global _redis
    if _redis:
        await cast(Awaitable[Any], _redis.aclose())
        _redis = None
        log.info("redis.disconnected")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


# ── Cache key builders (centralised naming) ───────────────────────────────────

def key_horoscope(sign: str, date: str, period: str) -> str:
    return f"horoscope:{sign}:{date}:{period}"

def key_natal(user_id: int) -> str:
    return f"natal:{user_id}"

def key_natal_pdf_download(token: str) -> str:
    return f"natal:pdf-download:{token}"

def key_destiny_pdf_download(token: str) -> str:
    return f"destiny:pdf-download:{token}"

def key_moon(date: str) -> str:
    return f"moon:{date}"

def key_user_premium(user_id: int) -> str:
    return f"user:premium:{user_id}"

def key_tarot_interpret(reading_id: int) -> str:
    return f"tarot:interpret:{reading_id}"


# ── Generic helpers ───────────────────────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def cache_set(key: str, value: Any, ttl: int) -> None:
    r = get_redis()
    serialised = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    await r.setex(key, ttl, serialised)


async def cache_delete(key: str) -> None:
    await cast(Awaitable[Any], get_redis().delete(key))
