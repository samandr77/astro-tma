"""User profile endpoints."""

from typing import Any, TypedDict

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.user import (
    SetGenderRequest,
    SetPushRequest,
    SetupBirthDataRequest,
    SetupBirthDataResponse,
    UserProfile,
)
from core.cache import cache_delete, key_natal
from core.logging import get_logger
from db.database import get_db
from db.models import Gender, Purchase, Subscription, SubscriptionStatus, ZodiacSign
from services.astro.natal import calculate_natal, chart_to_json
from services.payments.stars import LEGACY_PRODUCT_NAMES_RU, PRODUCTS
from services.users import repository as user_repo

router = APIRouter(prefix="/users", tags=["users"])
log = get_logger(__name__)


class GeoResult(TypedDict):
    city: str
    lat: float
    lng: float
    tz: str


# Sun sign → ZodiacSign enum mapping (Kerykeion returns English names)
_SIGN_MAP: dict[str, ZodiacSign] = {s.value: s for s in ZodiacSign}
_KERY_TO_ENUM: dict[str, ZodiacSign] = {
    "Aries": ZodiacSign.ARIES, "Taurus": ZodiacSign.TAURUS,
    "Gemini": ZodiacSign.GEMINI, "Cancer": ZodiacSign.CANCER,
    "Leo": ZodiacSign.LEO, "Virgo": ZodiacSign.VIRGO,
    "Libra": ZodiacSign.LIBRA, "Scorpio": ZodiacSign.SCORPIO,
    "Sagittarius": ZodiacSign.SAGITTARIUS, "Capricorn": ZodiacSign.CAPRICORN,
    "Aquarius": ZodiacSign.AQUARIUS, "Pisces": ZodiacSign.PISCES,
}


@router.post("/me", response_model=UserProfile)
async def upsert_me(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called on every Mini App launch to sync Telegram user data.
    Creates user on first launch, updates Telegram fields on subsequent ones.
    """
    user, created = await user_repo.get_or_create(
        db,
        tg_user_id=tg_user["id"],
        first_name=tg_user.get("first_name", ""),
        username=tg_user.get("username"),
        last_name=tg_user.get("last_name"),
        language_code=tg_user.get("language_code", "ru"),
        is_premium=tg_user.get("is_premium", False),
    )

    is_prem = await user_repo.is_premium(db, user.id)

    return UserProfile(
        id=user.id,
        name=user.tg_first_name,
        gender=user.gender.value if user.gender else None,
        sun_sign=user.sun_sign.value if user.sun_sign else None,
        birth_city=user.birth_city,
        birth_time_known=user.birth_time_known,
        push_enabled=user.push_enabled,
        is_premium=is_prem,
        created_at=user.created_at,
    )


@router.post("/me/gender", response_model=UserProfile)
async def set_gender(
    body: SetGenderRequest,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Set user gender."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    gender_enum = Gender(body.gender)
    user.gender = gender_enum
    await db.commit()

    is_prem = await user_repo.is_premium(db, user.id)
    return UserProfile(
        id=user.id,
        name=user.tg_first_name,
        gender=user.gender.value if user.gender else None,
        sun_sign=user.sun_sign.value if user.sun_sign else None,
        birth_city=user.birth_city,
        birth_time_known=user.birth_time_known,
        push_enabled=user.push_enabled,
        is_premium=is_prem,
        created_at=user.created_at,
    )


@router.get("/me/purchases")
async def get_my_purchases(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the user's one-time purchases and active subscription (if any).
    Used by the "Мои покупки" block on the Profile screen."""
    user_id = tg_user["id"]

    purchase_rows = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == user_id)
        .order_by(Purchase.created_at.desc())
    )
    purchases_out: list[dict[str, Any]] = []
    for p in purchase_rows.scalars().all():
        meta = PRODUCTS.get(p.product_id, {})
        product_name = (
            meta.get("name")
            or LEGACY_PRODUCT_NAMES_RU.get(p.product_id)
            or p.product_id
        )
        purchases_out.append({
            "product_id": p.product_id,
            "product_name": product_name,
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "stars_amount": p.stars_amount,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    from datetime import UTC, datetime
    now = datetime.now(UTC)
    sub_rows = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )
    subscriptions_out: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for s in sub_rows.scalars().all():
        item = {
            "plan": s.plan.value if hasattr(s.plan, "value") else str(s.plan),
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "stars_paid": s.stars_paid,
            "starts_at": s.starts_at.isoformat() if s.starts_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "is_trial": bool(getattr(s, "is_trial", False)),
            "trial_reason": getattr(s, "trial_reason", None),
        }
        subscriptions_out.append(item)
        if (
            active is None
            and s.status == SubscriptionStatus.ACTIVE
            and s.expires_at
            and s.expires_at > now
        ):
            active = item

    return {
        "purchases": purchases_out,
        "subscriptions": subscriptions_out,
        "active_subscription": active,
    }


@router.patch("/me/push", response_model=UserProfile)
async def set_push_enabled(
    body: SetPushRequest,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle push notifications for the current user."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.push_enabled = body.enabled
    await db.commit()

    is_prem = await user_repo.is_premium(db, user.id)
    return UserProfile(
        id=user.id,
        name=user.tg_first_name,
        gender=user.gender.value if user.gender else None,
        sun_sign=user.sun_sign.value if user.sun_sign else None,
        birth_city=user.birth_city,
        birth_time_known=user.birth_time_known,
        push_enabled=user.push_enabled,
        is_premium=is_prem,
        created_at=user.created_at,
    )


@router.post("/me/birth", response_model=SetupBirthDataResponse)
async def setup_birth_data(
    body: SetupBirthDataRequest,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Set or update user's birth data.
    Triggers natal chart (re)calculation.
    Geocodes city via GeoNames API.
    """
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Use pre-resolved coordinates if provided, otherwise geocode
    if body.lat is not None and body.lng is not None:
        tz = await _get_timezone(body.lat, body.lng)
        geo: GeoResult = {"city": body.birth_city, "lat": body.lat, "lng": body.lng, "tz": tz}
        log.info("geocode.from_client", city=body.birth_city, lat=body.lat, lng=body.lng)
    else:
        geo = await _geocode_city(body.birth_city)

    # Calculate natal chart
    chart = None
    try:
        chart = calculate_natal(
            name=user.tg_first_name,
            birth_dt=body.birth_date,
            lat=geo["lat"],
            lng=geo["lng"],
            tz_str=geo["tz"],
            birth_time_known=body.birth_time_known,
        )
    except Exception as e:
        log.error("natal.calculation_failed", user_id=user.id, error=str(e))

    sun_sign_enum = (
        _KERY_TO_ENUM.get(chart.sun.sign, ZodiacSign.ARIES)
        if chart and chart.sun and chart.sun.sign
        else ZodiacSign.ARIES
    )

    # Persist birth data
    await user_repo.update_birth_data(
        db, user,
        birth_date=body.birth_date,
        birth_time_known=body.birth_time_known,
        birth_city=geo["city"],
        lat=geo["lat"],
        lng=geo["lng"],
        tz_str=geo["tz"],
        sun_sign=sun_sign_enum,
    )

    # Persist natal chart only if calculation succeeded
    if chart:
        await user_repo.save_natal_chart(
            db,
            user_id=user.id,
            sun_sign=chart.sun.sign if chart.sun else "",
            moon_sign=chart.moon.sign if chart.moon else "",
            ascendant_sign=chart.ascendant_sign,
            chart_data=chart_to_json(chart),
        )

    # Invalidate caches
    await cache_delete(key_natal(user.id))

    return SetupBirthDataResponse(
        sun_sign=sun_sign_enum.value,
        moon_sign=chart.moon.sign if chart and chart.moon else "",
        ascendant_sign=chart.ascendant_sign if chart else None,
        city_resolved=geo["city"],
        lat=geo["lat"],
        lng=geo["lng"],
    )


async def _get_timezone(lat: float, lng: float) -> str:
    """Resolve timezone from coordinates via timeapi.io (free, no key)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://timeapi.io/api/timezone/coordinate",
                params={"latitude": lat, "longitude": lng},
            )
        data = resp.json()
        return data.get("timeZone", "UTC")
    except Exception:
        return "UTC"


_GEOCODE_PLACE_PRIORITY = {
    # First match wins — prefer real inhabited places over admin areas
    "city": 5,
    "town": 5,
    "village": 4,
    "hamlet": 3,
    "suburb": 2,
    "municipality": 1,
    "administrative": 0,
}


def _place_score(result: dict) -> int:
    """Higher score = more likely to be the actual settlement the user
    typed in, rather than an enclosing admin region."""
    pclass = (result.get("class") or "").lower()
    ptype = (result.get("type") or "").lower()

    addr = result.get("address", {}) or {}
    if addr.get("city"):
        return _GEOCODE_PLACE_PRIORITY["city"]
    if addr.get("town"):
        return _GEOCODE_PLACE_PRIORITY["town"]
    if addr.get("village"):
        return _GEOCODE_PLACE_PRIORITY["village"]
    if addr.get("hamlet"):
        return _GEOCODE_PLACE_PRIORITY["hamlet"]
    if pclass == "place" and ptype in _GEOCODE_PLACE_PRIORITY:
        return _GEOCODE_PLACE_PRIORITY[ptype]
    if pclass == "boundary" or ptype == "administrative":
        return _GEOCODE_PLACE_PRIORITY["administrative"]
    return 0


def _place_name(result: dict, fallback: str) -> str:
    addr = result.get("address", {}) or {}
    return (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("hamlet")
        or addr.get("municipality")
        or result.get("name")
        or fallback
    )


async def _geocode_city(city: str) -> GeoResult:
    """
    Resolve city name to lat/lng/tz via Nominatim (OpenStreetMap).
    Asks for several candidates and picks the one that's actually a
    settlement (city/town/village), not an administrative area — fixes
    cases like "Марьина Горка" silently resolving to the surrounding
    rural soviet boundary instead of the town itself.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": city,
                    "format": "json",
                    "limit": 5,
                    "addressdetails": 1,
                    "accept-language": "ru",
                },
                headers={"User-Agent": "astro-tma/1.0"},
            )
        data = resp.json()
        if data:
            ranked = sorted(data, key=_place_score, reverse=True)
            place = ranked[0]
            lat = float(place["lat"])
            lng = float(place["lon"])
            name = _place_name(place, city)
            tz = await _get_timezone(lat, lng)
            log.info(
                "geocode.ok",
                city=name,
                lat=lat,
                lng=lng,
                tz=tz,
                candidates=len(data),
                score=_place_score(place),
            )
            return {"city": name, "lat": lat, "lng": lng, "tz": tz}
    except Exception as e:
        log.warning("geocode.failed", city=city, error=str(e))

    # Default fallback
    log.warning("geocode.fallback_moscow", city=city)
    return {"city": city, "lat": 55.7558, "lng": 37.6176, "tz": "Europe/Moscow"}
