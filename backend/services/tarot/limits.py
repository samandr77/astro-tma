"""Per-user Tarot spread limits.

Celtic Cross: every user gets 2 lifetime free reads. After that the
spread is gated behind tarot_celtic purchase or active Premium.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TarotReading

CELTIC_FREE_LIFETIME_LIMIT = 2


async def count_celtic_readings(db: AsyncSession, user_id: int) -> int:
    """Total Celtic Cross readings the user has ever performed."""
    result = await db.execute(
        select(func.count(TarotReading.id)).where(
            TarotReading.user_id == user_id,
            TarotReading.spread_type == "celtic_cross",
        )
    )
    return int(result.scalar_one() or 0)


async def celtic_free_remaining(db: AsyncSession, user_id: int) -> int:
    """How many free Celtic reads the user still has left. Clamped to [0, LIMIT]."""
    used = await count_celtic_readings(db, user_id)
    return max(0, CELTIC_FREE_LIFETIME_LIMIT - used)


async def can_user_do_celtic_for_free(db: AsyncSession, user_id: int) -> bool:
    return (await celtic_free_remaining(db, user_id)) > 0
