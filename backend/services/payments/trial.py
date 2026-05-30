"""Trial subscription management.

A "trial" is a Subscription row with `stars_paid = 0` and `is_trial = true`
that exists exactly so the existing `is_premium()` check (looks for any
ACTIVE subscription whose expires_at is in the future) lets the user into
Premium features without buying anything.

Two flavours of trial today:
- welcome (3 days, granted on user create)
- referral (extension of an existing trial by N days when the user applies
  a referral code in the first 24h)

`grant_trial_days` is idempotent in the sense that it extends an existing
active subscription rather than stacking new rows — but the *event* that
triggers it must be deduped by the caller (see User.referred_by_processed,
etc.) because multiple webhook firings or React-Query refetches could
otherwise hand out free days.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from db.models import Subscription, SubscriptionPlan, SubscriptionStatus

log = get_logger(__name__)


async def grant_trial_days(
    db: AsyncSession,
    user_id: int,
    days: int,
    reason: str,
) -> Subscription:
    """Grant N days of Premium to `user_id` as a trial.

    - No active subscription → create a new trial subscription.
    - Active TRIAL or PAID subscription → push its expires_at forward by `days`.

    Returns the resulting Subscription. Caller commits.
    """
    now = datetime.now(UTC)

    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
    )
    active = result.scalars().first()

    if active is not None:
        active.expires_at = active.expires_at + timedelta(days=days)
        await db.flush()
        log.info(
            "trial.extended",
            user_id=user_id,
            days=days,
            reason=reason,
            new_expires=active.expires_at.isoformat(),
        )
        return active

    expires = now + timedelta(days=days)
    fake_charge_id = f"trial_{user_id}_{int(now.timestamp())}_{reason}"
    sub = Subscription(
        user_id=user_id,
        plan=SubscriptionPlan.PREMIUM_MONTH,
        status=SubscriptionStatus.ACTIVE,
        stars_paid=0,
        tg_payment_charge_id=fake_charge_id,
        starts_at=now,
        expires_at=expires,
        is_trial=True,
        trial_reason=reason,
    )
    db.add(sub)
    await db.flush()
    log.info(
        "trial.granted",
        user_id=user_id,
        days=days,
        reason=reason,
        expires=expires.isoformat(),
    )
    return sub
