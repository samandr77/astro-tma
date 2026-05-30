"""Tarot spread endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.tarot import (
    _IMAGE_BASE,
    DrawSpreadRequest,
    TarotCardDetail,
    TarotHistoryItem,
    TarotInterpretationResponse,
    TarotPositionNarrative,
    TarotSpreadResponse,
)
from core.cache import cache_get, cache_set, key_tarot_interpret
from core.logging import get_logger
from core.periods import is_active_period, next_reset_at, now_utc, period_type_for_tarot
from core.settings import settings
from db.database import get_db
from db.models import TarotCard, TarotPositionMeaning, TarotReading
from services.tarot.engine import (
    PREMIUM_SPREADS,
    SPREADS,
    draw_spread,
    to_reading_json,
)
from services.tarot.interpreter import (
    expected_card_count,
    generate_spread_interpretation,
    is_supported_spread,
)
from services.users import repository as user_repo

router = APIRouter(prefix="/tarot", tags=["tarot"])
log = get_logger(__name__)


async def _build_spread_response(
    db: AsyncSession,
    reading: TarotReading,
    *,
    reused_existing: bool = False,
) -> TarotSpreadResponse:
    cards_json = reading.cards_json or []
    drawn_ids = [c["card_id"] for c in cards_json]

    cards_result = await db.execute(
        select(TarotCard).where(TarotCard.id.in_(drawn_ids))
    )
    cards_map: dict[int, TarotCard] = {c.id: c for c in cards_result.scalars()}

    pos_result = await db.execute(
        select(TarotPositionMeaning).where(
            TarotPositionMeaning.spread_type == reading.spread_type,
            TarotPositionMeaning.card_id.in_(drawn_ids),
        )
    )
    pos_meanings: dict[tuple[int, int], str] = {}
    pos_names: dict[tuple[int, int], str] = {}
    for pm in pos_result.scalars():
        pos_meanings[(pm.card_id, pm.position)] = pm.meaning_ru
        pos_names[(pm.card_id, pm.position)] = pm.position_name_ru

    card_details: list[TarotCardDetail] = []
    for drawn in sorted(cards_json, key=lambda x: x.get("position", 0)):
        card = cards_map.get(drawn["card_id"])
        if not card:
            continue
        reversed_flag = bool(drawn.get("reversed"))
        meaning = card.reversed_ru if reversed_flag else card.upright_ru
        position = drawn["position"]
        fallback_position_name = ""
        spread_positions = SPREADS.get(reading.spread_type)
        if spread_positions and 0 <= position < len(spread_positions):
            fallback_position_name = spread_positions[position].name_ru
        card_details.append(
            TarotCardDetail(
                id=card.id,
                name_ru=card.name_ru,
                name_en=card.name_en,
                emoji=card.emoji,
                arcana=card.arcana.value,
                reversed=reversed_flag,
                meaning_ru=meaning,
                position_name_ru=fallback_position_name or pos_names.get((card.id, position), ""),
                position_meaning_ru=pos_meanings.get((card.id, position)),
                keywords_ru=card.keywords_ru or [],
                image_url=(_IMAGE_BASE + card.image_key) if card.image_key else None,
            )
        )

    period_type = period_type_for_tarot(reading.spread_type)
    return TarotSpreadResponse(
        reading_id=reading.id,
        spread_type=reading.spread_type,
        cards=card_details,
        is_premium=reading.spread_type in PREMIUM_SPREADS,
        next_reset_at=next_reset_at(reading.created_at, period_type),
        reused_existing=reused_existing,
        period_type=period_type,
    )


@router.post("/draw", response_model=TarotSpreadResponse)
async def draw_tarot(
    body: DrawSpreadRequest,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Draw a tarot spread.
    Free spreads: three_card (once per day).
    All spread types are free for every user — the lifetime/subscription
    paywall on Tarot was removed by product. (PREMIUM_SPREADS / celtic
    lifetime-limit checks intentionally skipped here.)
    """
    spread_type = body.spread_type
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    from services.ratelimit import LIMITS, enforce_monthly_limit

    period_type = period_type_for_tarot(spread_type)
    latest_result = await db.execute(
        select(TarotReading)
        .where(
            TarotReading.user_id == user.id,
            TarotReading.spread_type == spread_type,
        )
        .order_by(TarotReading.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    if latest and is_active_period(latest.created_at, period_type, now=now_utc()):
        return await _build_spread_response(db, latest, reused_existing=True)

    # Monthly fair-use cap (don't count reused readings — only fresh draws).
    await enforce_monthly_limit(
        user.id, "tarot_draw", LIMITS["tarot_draw"], feature_ru="расклады Таро",
    )

    # Load all card IDs
    result = await db.execute(select(TarotCard.id))
    card_ids = [row[0] for row in result.all()]

    if not card_ids:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Tarot deck not seeded")

    # Draw cards
    drawn = draw_spread(spread_type, card_ids)

    # Save reading to history
    reading = TarotReading(
        user_id=user.id,
        spread_type=spread_type,
        cards_json=to_reading_json(drawn),
    )
    db.add(reading)
    await db.flush()
    await db.refresh(reading)

    return await _build_spread_response(db, reading)


@router.get("/celtic/status")
async def get_celtic_status(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Kept for frontend back-compat after the Celtic Cross paywall was
    removed. Always reports that the spread is free and the gate is off."""
    _ = tg_user, db  # parameters retained for the dependency contract
    return {
        "free_remaining": 99,
        "free_limit": 99,
        "has_purchased": False,
        "is_premium": False,
        "needs_gate": False,
    }


@router.get("/history", response_model=list[TarotHistoryItem])
async def get_reading_history(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Last 30 readings for this user with card name previews."""
    result = await db.execute(
        select(TarotReading)
        .where(TarotReading.user_id == tg_user["id"])
        .order_by(TarotReading.created_at.desc())
        .limit(30)
    )
    readings = list(result.scalars())
    if not readings:
        return []

    # Gather all card ids referenced, then resolve names in one query
    all_ids: set[int] = set()
    for r in readings:
        for c in (r.cards_json or []):
            all_ids.add(c["card_id"])

    names_result = await db.execute(
        select(TarotCard.id, TarotCard.name_ru).where(TarotCard.id.in_(all_ids))
    )
    names = {row[0]: row[1] for row in names_result.all()}

    items: list[TarotHistoryItem] = []
    for r in readings:
        cards_json = r.cards_json or []
        sorted_cards = sorted(cards_json, key=lambda x: x.get("position", 0))
        previews = [names.get(c["card_id"], "?") for c in sorted_cards[:3]]
        items.append(
            TarotHistoryItem(
                reading_id=r.id,
                spread_type=r.spread_type,
                card_count=len(cards_json),
                card_previews=previews,
                created_at=r.created_at,
            )
        )
    return items


@router.get("/readings/{reading_id}", response_model=TarotSpreadResponse)
async def get_reading_by_id(
    reading_id: int,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-open a past reading with full card details."""
    reading = await db.get(TarotReading, reading_id)
    if not reading or reading.user_id != tg_user["id"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reading not found")

    return await _build_spread_response(db, reading)


@router.post("/interpret/{reading_id}", response_model=TarotInterpretationResponse)
async def interpret_reading(
    reading_id: int,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate (or return cached) LLM narrative interpretation for a reading.
    Supports three_card, celtic_cross, week, relationship. Each subsequent
    card is read in the context of previously drawn ones.
    """
    # Load reading and verify ownership
    reading = await db.get(TarotReading, reading_id)
    if not reading or reading.user_id != tg_user["id"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reading not found")

    if not is_supported_spread(reading.spread_type):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Interpretation not supported for {reading.spread_type}",
        )

    # Cache by reading_id — interpretation is deterministic for a given reading
    cache_key = key_tarot_interpret(reading.id)
    cached = await cache_get(cache_key)
    if cached:
        return TarotInterpretationResponse(**cached)

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Interpretation service is not configured",
        )

    # Resolve cards_json -> card details needed for the prompt
    cards_json = reading.cards_json or []
    expected_n = expected_card_count(reading.spread_type)
    drawn_ids = [c["card_id"] for c in cards_json]
    if len(drawn_ids) != expected_n:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Reading has unexpected card count (got {len(drawn_ids)}, expected {expected_n})",
        )

    cards_result = await db.execute(select(TarotCard).where(TarotCard.id.in_(drawn_ids)))
    cards_map: dict[int, TarotCard] = {c.id: c for c in cards_result.scalars()}

    prompt_cards: list[dict] = []
    for drawn in sorted(cards_json, key=lambda x: x["position"]):
        card = cards_map.get(drawn["card_id"])
        if not card:
            continue
        prompt_cards.append(
            {
                "name_ru": card.name_ru,
                "reversed": bool(drawn.get("reversed")),
                "keywords_ru": card.keywords_ru or [],
            }
        )

    try:
        parsed = await generate_spread_interpretation(
            spread_type=reading.spread_type,
            cards=prompt_cards,
            api_key=settings.ANTHROPIC_API_KEY,
        )
    except Exception as e:  # noqa: BLE001
        log.error(
            "tarot.interpret.failed",
            reading_id=reading.id,
            spread=reading.spread_type,
            error=str(e),
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Interpretation failed — please try again",
        ) from e

    response = TarotInterpretationResponse(
        reading_id=reading.id,
        spread_type=reading.spread_type,
        positions=[TarotPositionNarrative(**p) for p in parsed["positions"]],
        summary=parsed["summary"],
    )

    await cache_set(cache_key, response.model_dump(), settings.CACHE_TTL_TAROT_INTERPRET)
    return response
