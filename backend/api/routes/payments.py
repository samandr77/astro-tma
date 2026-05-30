"""Payment endpoints — Telegram Stars flow."""


from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.payments import (
    CreateInvoiceRequest,
    CreateInvoiceResponse,
    ProductInfo,
)
from core.logging import get_logger
from core.settings import settings
from db.database import get_db
from services.payments.pricing import get_product_price
from services.payments.stars import (
    PRODUCTS,
    create_invoice_link,
    grant_product_access,
    handle_pre_checkout,
)

router = APIRouter(prefix="/payments", tags=["payments"])
log = get_logger(__name__)


@router.get("/products", response_model=list[ProductInfo])
async def list_products(tg_user: dict = Depends(get_tg_user)):
    """Return all purchasable products with current Stars prices."""
    out: list[ProductInfo] = []
    for pid, p in PRODUCTS.items():
        stars = await get_product_price(pid, default=p["stars"])
        out.append(
            ProductInfo(
                id=pid,
                name=p["name"],
                description=p["description"],
                stars=stars,
                type=p["type"],
            )
        )
    return out


@router.post("/invoice", response_model=CreateInvoiceResponse)
async def create_invoice(
    body: CreateInvoiceRequest,
    tg_user: dict = Depends(get_tg_user),
):
    """Create a Telegram Stars invoice link for the given product."""
    invoice_url = await create_invoice_link(tg_user["id"], body.product_id)
    product = PRODUCTS[body.product_id]
    return CreateInvoiceResponse(
        invoice_url=invoice_url,
        product_id=body.product_id,
        stars_amount=product["stars"],
    )


@router.post("/webhook")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Telegram Bot API webhook receiver.
    Handles: pre_checkout_query, successful_payment.

    Security: Telegram signs the webhook URL secret in the header.
    We verify X-Telegram-Bot-Api-Secret-Token matches our configured secret.
    """
    # Verify webhook secret
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        log.warning("webhook.invalid_secret")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook secret")

    body = await request.json()
    log.debug("webhook.received", update_keys=list(body.keys()))

    # ── Pre-checkout query: must answer within 10 seconds ──────────────────
    if "pre_checkout_query" in body:
        pcq = body["pre_checkout_query"]
        await handle_pre_checkout(pcq["id"], ok=True)
        return {"ok": True}

    # ── Successful payment ─────────────────────────────────────────────────
    message = body.get("message", {})
    if "successful_payment" in message:
        sp = message["successful_payment"]
        user_id = message["from"]["id"]
        payload: str = sp["invoice_payload"]
        charge_id: str = sp["telegram_payment_charge_id"]

        # payload format: "{user_id}:{product_id}:{timestamp}"
        try:
            _, product_id, _ = payload.split(":")
        except ValueError:
            log.error("webhook.bad_payload", payload=payload)
            return {"ok": True}  # Return 200 anyway so Telegram doesn't retry

        try:
            await grant_product_access(db, user_id, product_id, charge_id, payload)
            log.info("webhook.payment_processed", user_id=user_id, product=product_id)
        except IntegrityError:
            # SECURITY_AUDIT.md H2 — Telegram retries successful_payment on
            # any 5xx response; tg_payment_charge_id has UNIQUE constraint
            # so the second INSERT raises IntegrityError. Roll back and
            # ack 200 — the original payment is already granted.
            await db.rollback()
            log.info(
                "webhook.payment_duplicate_ignored",
                user_id=user_id, product=product_id, charge_id=charge_id,
            )

    return {"ok": True}
