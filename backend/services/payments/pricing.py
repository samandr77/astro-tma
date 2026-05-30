"""Effective Stars-price resolution with Redis-backed overrides.

The catalogue in `services.payments.stars.PRODUCTS` carries the *default*
price for each product. Admins can override the default at runtime via
the admin UI; the override lives in Redis so changes are picked up by
every backend worker without a restart.

Cache key shape:
    price_override:{product_id}   →  int (Stars amount)
"""

from __future__ import annotations

from typing import Any

from core.cache import cache_delete, cache_get, cache_set

# 1 year — overrides are effectively permanent until cleared.
_OVERRIDE_TTL = 86400 * 365


def _key(product_id: str) -> str:
    return f"price_override:{product_id}"


def _normalize_override(value: Any) -> int | None:
    """Allow ints, numeric strings, and `{"stars": int}` shapes (older
    Redis snapshots) — anything we can confidently coerce to a positive
    integer."""
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, str):
        try:
            n = int(value)
            return n if n >= 1 else None
        except ValueError:
            return None
    if isinstance(value, dict):
        return _normalize_override(value.get("stars"))
    return None


async def get_product_price(product_id: str, default: int) -> int:
    """Effective price: Redis override → catalogue default."""
    override = await cache_get(_key(product_id))
    parsed = _normalize_override(override)
    return parsed if parsed is not None else default


async def set_product_price(product_id: str, stars: int) -> None:
    if stars < 1:
        raise ValueError("Stars amount must be a positive integer")
    await cache_set(_key(product_id), stars, _OVERRIDE_TTL)


async def clear_product_price(product_id: str) -> None:
    await cache_delete(_key(product_id))


async def get_all_overrides(product_ids: list[str]) -> dict[str, int | None]:
    """Bulk fetch of overrides for the catalogue. Missing → None."""
    out: dict[str, int | None] = {}
    for pid in product_ids:
        raw = await cache_get(_key(pid))
        out[pid] = _normalize_override(raw)
    return out
