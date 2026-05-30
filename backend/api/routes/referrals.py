"""Referral programme endpoints (Model B — paid-conversion)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from core.logging import get_logger
from core.settings import settings
from db.database import get_db
from db.models import (
    Purchase,
    PurchaseStatus,
    ReferralReward,
    Subscription,
    User,
)
from services.payments.trial import grant_trial_days
from services.referrals.code import get_or_create_referral_code
from services.users import repository as user_repo

log = get_logger(__name__)
router = APIRouter(prefix="/referrals", tags=["referrals"])


class ApplyReferralRequest(BaseModel):
    code: str


class ApplyReferralResponse(BaseModel):
    success: bool
    days_granted: int
    message: str


class ReferralStats(BaseModel):
    invited_total: int
    purchased: int
    days_earned: int


class ReferralInfoResponse(BaseModel):
    code: str
    invite_url: str
    stats: ReferralStats


def _build_invite_url(code: str) -> str:
    bot = (settings.TELEGRAM_BOT_USERNAME or "").lstrip("@")
    if not bot:
        return ""
    return f"https://t.me/{bot}?start=ref_{code}"


@router.get("/me", response_model=ReferralInfoResponse)
async def get_my_referral_info(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = tg_user["id"]
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    code = await get_or_create_referral_code(db, user_id)
    await db.commit()

    invited_total = (
        await db.execute(select(func.count(User.id)).where(User.referred_by == user_id))
    ).scalar_one() or 0
    purchased = (
        await db.execute(
            select(func.count(distinct(User.id)))
            .select_from(User)
            .join(Purchase, Purchase.user_id == User.id)
            .where(
                User.referred_by == user_id,
                Purchase.status == PurchaseStatus.COMPLETED,
                Purchase.stars_amount > 0,
            )
        )
    ).scalar_one() or 0
    days_earned = (
        await db.execute(
            select(func.coalesce(func.sum(ReferralReward.days_granted), 0)).where(
                ReferralReward.referrer_id == user_id,
                ReferralReward.event_type == "first_purchase_referrer_bonus",
            )
        )
    ).scalar_one() or 0

    return ReferralInfoResponse(
        code=code,
        invite_url=_build_invite_url(code),
        stats=ReferralStats(
            invited_total=int(invited_total),
            purchased=int(purchased),
            days_earned=int(days_earned),
        ),
    )


@router.post("/apply", response_model=ApplyReferralResponse)
async def apply_referral(
    body: ApplyReferralRequest,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Frontend posts here once on first launch if start_param starts with `ref_`.
    Extends the referee's welcome trial; referrer earns nothing yet —
    that bonus is triggered later by `grant_product_access`."""
    if not settings.FEATURE_REFERRAL_PROGRAM:
        return ApplyReferralResponse(
            success=False,
            days_granted=0,
            message="Реферальная программа отключена",
        )

    referral_code = body.code.lower().strip()
    user_id = tg_user["id"]

    # 1. Validate code
    referrer = (
        await db.execute(select(User).where(User.referral_code == referral_code))
    ).scalar_one_or_none()
    if not referrer:
        return ApplyReferralResponse(
            success=False,
            days_granted=0,
            message="Код не найден",
        )

    # 2. Self-referral
    if referrer.id == user_id:
        return ApplyReferralResponse(
            success=False,
            days_granted=0,
            message="Нельзя пригласить самого себя",
        )

    # 3. Get referee
    referee = await user_repo.get_by_id(db, user_id)
    if not referee:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # 4. Already referred — silent no-op
    if referee.referred_by is not None:
        return ApplyReferralResponse(
            success=False,
            days_granted=0,
            message="Код уже применён ранее",
        )

    # 5. 24h window — fresh accounts only
    created_at = referee.created_at
    if created_at and (datetime.now(UTC) - created_at).total_seconds() > 86400:
        return ApplyReferralResponse(
            success=False,
            days_granted=0,
            message="Код можно применить только в первые 24 часа после регистрации",
        )

    # 6. Link the referrer
    referee.referred_by = referrer.id
    referee.referred_by_processed = True

    # 7. Extend the welcome trial (welcome 3 + extension 4 = 7 total)
    days = settings.REFERRAL_TRIAL_EXTENSION_DAYS
    await grant_trial_days(
        db,
        user_id=referee.id,
        days=days,
        reason="referral_signup_referee",
    )

    # 8. Audit row — UniqueConstraint protects against repeated calls
    db.add(
        ReferralReward(
            referrer_id=referrer.id,
            referee_id=referee.id,
            event_type="signup_referee_bonus",
            days_granted=days,
        )
    )

    await db.commit()
    log.info(
        "referral.applied",
        referrer=referrer.id,
        referee=referee.id,
        days=days,
    )
    return ApplyReferralResponse(
        success=True,
        days_granted=days,
        message=f"Премиум продлён на {days} дней",
    )


async def maybe_award_first_purchase(
    db: AsyncSession,
    referee_user_id: int,
    referee_first_name: str | None,
    product_id: str,
) -> None:
    """Called from `grant_product_access` AFTER the new Purchase/Subscription
    row has been flushed. If this is the user's FIRST paid action and they
    were referred, hand the referrer their bonus.
    """
    if not settings.FEATURE_REFERRAL_PROGRAM:
        return

    # Count only real (paid) actions — trials must not count.
    paid_purchases = (
        await db.execute(
            select(func.count(Purchase.id)).where(
                Purchase.user_id == referee_user_id,
                Purchase.status == PurchaseStatus.COMPLETED,
                Purchase.stars_amount > 0,
            )
        )
    ).scalar_one() or 0
    paid_subs = (
        await db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.user_id == referee_user_id,
                Subscription.stars_paid > 0,
            )
        )
    ).scalar_one() or 0
    total = int(paid_purchases) + int(paid_subs)
    if total != 1:
        return  # not exactly the first paid action

    user = await user_repo.get_by_id(db, referee_user_id)
    if not user or not user.referred_by:
        return
    if user.referred_purchase_processed:
        return  # already paid out — extra safety

    bonus = settings.REFERRAL_FIRST_PURCHASE_BONUS_DAYS
    try:
        await grant_trial_days(
            db,
            user_id=user.referred_by,
            days=bonus,
            reason="referral_first_purchase",
        )
        db.add(
            ReferralReward(
                referrer_id=user.referred_by,
                referee_id=user.id,
                event_type="first_purchase_referrer_bonus",
                days_granted=bonus,
            )
        )
        user.referred_purchase_processed = True
        await db.flush()
        log.info(
            "referral.first_purchase_bonus",
            referrer=user.referred_by,
            referee=user.id,
            product=product_id,
            days=bonus,
        )
    except Exception as e:  # noqa: BLE001
        # If the UniqueConstraint fires, just bail — the bonus was already
        # paid out in a parallel transaction.
        log.warning(
            "referral.bonus_grant_failed",
            referrer=user.referred_by,
            referee=user.id,
            error=str(e),
        )
        return

    # Best-effort Telegram notification — separate try because we don't
    # want a sendMessage hiccup to roll back the bonus grant.
    try:
        from services.referrals.notifications import notify_referrer_of_bonus

        await notify_referrer_of_bonus(
            referrer_id=user.referred_by,
            referee_name=referee_first_name or "ваш друг",
            days=bonus,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "referral.notify_dispatch_failed",
            referrer=user.referred_by,
            error=str(e),
        )
