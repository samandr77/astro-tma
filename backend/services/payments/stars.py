"""
Telegram Stars payment service.

Flow:
  1. Client requests invoice  →  create_invoice_link()
  2. Client opens invoice     →  WebApp.openInvoice()
  3. Telegram sends webhook   →  handle_pre_checkout() + handle_successful_payment()
  4. We grant access          →  grant_product_access()

ALL access grants happen in webhook handler — never trust client callback alone.
"""

import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.settings import settings
from db.models import (
    Purchase,
    PurchaseStatus,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)

log = get_logger(__name__)

# ── Product catalogue ─────────────────────────────────────────────────────────
# Launch monetization v1.1: horoscope_*, tarot_week, transits_*_preview were
# retired (gateways moved to the subscription). Existing rows in `purchases`
# for those product_ids stay in the DB for historical accuracy.
# Russian display names for retired SKUs — purchase rows for these still
# live in the DB and need a humane title on the "Мои покупки" screen.
LEGACY_PRODUCT_NAMES_RU: dict[str, str] = {
    "horoscope_tomorrow":       "Гороскоп на завтра",
    "horoscope_week":           "Гороскоп на неделю",
    "horoscope_month":          "Гороскоп на месяц",
    "tarot_celtic":             "Расклад Кельтский Крест",
    "tarot_week":               "Карты на неделю",
    "transits_week_preview":    "Транзиты на неделю",
    "transits_month_preview":   "Транзиты на месяц",
}


PRODUCTS: dict[str, dict] = {
    "natal_full": {
        "name": "Полная натальная карта",
        "description": "Длинные интерпретации планет/домов/аспектов + персональный портрет + PDF",
        "stars": settings.PRICE_NATAL_FULL,
        "type": "one_time",
    },
    "synastry": {
        "name": "Синастрия — детальный анализ",
        "description": "Глубокий анализ совместимости двух натальных карт",
        "stars": settings.PRICE_SYNASTRY,
        "type": "one_time",
    },
    "subscription_month": {
        "name": "Premium — 30 дней",
        "description": "Все интерпретации, прогнозы на неделю и месяц, Таро на неделю, push о значимых транзитах",
        "stars": settings.PRICE_SUBSCRIPTION_MONTH,
        "type": "subscription",
        "duration_days": 30,
        "plan": SubscriptionPlan.PREMIUM_MONTH,
    },
    "subscription_year": {
        "name": "Premium — 365 дней",
        "description": "Всё то же, что в месячной, но на год. Выгода 38%.",
        "stars": settings.PRICE_SUBSCRIPTION_YEAR,
        "type": "subscription",
        "duration_days": 365,
        "plan": SubscriptionPlan.PREMIUM_YEAR,
    },
}


async def create_invoice_link(user_id: int, product_id: str) -> str:
    """
    Call Telegram Bot API to create an invoice link for Stars payment.
    Returns the invoice URL to pass to WebApp.openInvoice().
    """
    if product_id not in PRODUCTS:
        raise ValueError(f"Unknown product: {product_id!r}")

    # Lazy import to avoid circular dependency between pricing and stars.
    from services.payments.pricing import get_product_price

    product = PRODUCTS[product_id]
    stars_amount = await get_product_price(product_id, default=product["stars"])

    # Payload encodes user + product + timestamp for webhook verification
    payload = f"{user_id}:{product_id}:{int(time.time())}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/createInvoiceLink",
            json={
                "title": product["name"],
                "description": product["description"],
                "payload": payload,
                "provider_token": "",  # MUST be empty for Stars
                "currency": "XTR",  # Telegram Stars
                "prices": [{"label": product["name"], "amount": stars_amount}],
            },
        )

    data = resp.json()
    if not data.get("ok"):
        log.error("stars.invoice_failed", product=product_id, response=data)
        raise RuntimeError(f"Telegram API error: {data.get('description')}")

    invoice_url: str = data["result"]
    log.info(
        "stars.invoice_created",
        user_id=user_id,
        product=product_id,
        stars=stars_amount,
    )
    return invoice_url


async def handle_pre_checkout(query_id: str, ok: bool = True, error: str | None = None) -> None:
    """
    Must be answered within 10 seconds of receiving pre_checkout_query.
    Decline here if product is invalid or user ineligible.
    """
    async with httpx.AsyncClient(timeout=8.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerPreCheckoutQuery",
            json={
                "pre_checkout_query_id": query_id,
                "ok": ok,
                **({"error_message": error} if error else {}),
            },
        )
    log.info("stars.pre_checkout_answered", query_id=query_id, ok=ok)


async def grant_product_access(
    db: AsyncSession,
    user_id: int,
    product_id: str,
    tg_payment_charge_id: str,
    payload: str,
) -> None:
    """
    Called after successful_payment webhook.
    Creates Purchase or Subscription record to unlock content.
    Idempotent — safe to call twice (unique constraint on charge_id).
    """
    if product_id not in PRODUCTS:
        log.warning("stars.unknown_product", product=product_id, user_id=user_id)
        return

    product = PRODUCTS[product_id]
    now = datetime.now(UTC)

    if product["type"] == "subscription":
        sub = Subscription(
            user_id=user_id,
            plan=product["plan"],
            status=SubscriptionStatus.ACTIVE,
            stars_paid=product["stars"],
            tg_payment_charge_id=tg_payment_charge_id,
            starts_at=now,
            expires_at=now + timedelta(days=product["duration_days"]),
        )
        db.add(sub)
    else:
        purchase = Purchase(
            user_id=user_id,
            product_id=product_id,
            status=PurchaseStatus.COMPLETED,
            stars_amount=product["stars"],
            tg_payment_charge_id=tg_payment_charge_id,
            payload=payload,
        )
        db.add(purchase)

    await db.flush()
    log.info(
        "stars.access_granted",
        user_id=user_id,
        product=product_id,
        charge_id=tg_payment_charge_id,
    )

    # Referral programme — Model B: pay the referrer when their friend
    # converts. Lazy import to avoid a circular dep between payments and
    # referrals routes.
    try:
        from sqlalchemy import select as _select

        from api.routes.referrals import maybe_award_first_purchase
        from db.models import User as _UserModel

        result = await db.execute(_select(_UserModel).where(_UserModel.id == user_id))
        u = result.scalar_one_or_none()
        await maybe_award_first_purchase(
            db,
            referee_user_id=user_id,
            referee_first_name=u.tg_first_name if u else None,
            product_id=product_id,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("referral.hook_failed", user_id=user_id, error=str(e))
