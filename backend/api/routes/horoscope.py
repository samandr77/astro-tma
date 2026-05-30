"""Horoscope, moon phase, and natal chart endpoints."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.horoscope import (
    EnergyScores,
    HoroscopeResponse,
    MoonCalendarDay,
    MoonCalendarResponse,
    MoonPhaseResponse,
)
from core.cache import (
    cache_get,
    cache_set,
    key_horoscope,
    key_moon,
)
from core.logging import get_logger
from core.settings import settings
from db.database import get_db
from services.astro.moon import get_monthly_calendar, get_moon_phase
from services.users import repository as user_repo

router = APIRouter(prefix="/horoscope", tags=["horoscope"])
log = get_logger(__name__)

# Russian sign names
_SIGN_RU: dict[str, str] = {
    "aries": "Овен", "taurus": "Телец", "gemini": "Близнецы",
    "cancer": "Рак", "leo": "Лев", "virgo": "Дева",
    "libra": "Весы", "scorpio": "Скорпион", "sagittarius": "Стрелец",
    "capricorn": "Козерог", "aquarius": "Водолей", "pisces": "Рыбы",
}

# Generic daily texts (fallback when no personalised text available)
_GENERIC_TEXTS: dict[str, str] = {
    "aries": "Сегодня Марс придаёт вам энергию и решимость. Идеальный день для новых начинаний.",
    "taurus": "Венера благоволит вашим финансовым делам. Будьте внимательны к деталям.",
    "gemini": "Меркурий активизирует общение. Важные переговоры пройдут успешно.",
    "cancer": "Луна в гармонии с вашим знаком усиливает интуицию. Доверяйте чувствам.",
    "leo": "Солнце освещает ваш творческий путь. Время заявить о себе.",
    "virgo": "Практичность и внимание к деталям принесут плоды. Ваш труд замечен.",
    "libra": "Венера создаёт гармонию в отношениях. Время для важных разговоров.",
    "scorpio": "Плутон усиливает вашу проницательность. Тайное становится явным.",
    "sagittarius": "Юпитер открывает новые горизонты. Расширяйте границы привычного.",
    "capricorn": "Сатурн укрепляет ваши позиции. Дисциплина принесёт результат.",
    "aquarius": "Уран приносит неожиданные озарения. Будьте открыты переменам.",
    "pisces": "Нептун усиливает творческое вдохновение. Следуйте своей мечте.",
}


_VALID_SIGNS = {
    "aries", "taurus", "gemini", "cancer", "leo", "virgo",
    "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
}


@router.get("/today", response_model=HoroscopeResponse)
async def get_today_horoscope(
    sign: str | None = Query(None, description="Override sign (lowercase EN)"),
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Today's horoscope. If `sign` query param is provided, returns the generic
    horoscope for that sign (used by the sign browser on the Horoscopes screen).
    Otherwise falls back to the user's sun sign and personalises with their
    natal chart if one exists. Free for all users. Cached per sign per day.
    """
    user = await user_repo.get_by_id(db, tg_user["id"])
    user_sign = user.sun_sign.value if (user and user.sun_sign) else "aries"
    requested = (sign or "").lower().strip()
    if requested and requested in _VALID_SIGNS:
        sign = requested
        # Browsing OTHER signs → never personalise; user-sign view still does.
        personalise = (requested == user_sign)
    else:
        sign = user_sign
        personalise = True
    today = date.today().isoformat()

    # Try personalised (if natal chart exists AND we're on the user's own sign)
    if personalise and user and user.natal_chart:
        return await _personalised_horoscope(user, sign, today, "today")

    # Generic sign horoscope — check cache first
    cache_key = key_horoscope(sign, today, "today")
    cached = await cache_get(cache_key)
    if cached:
        return HoroscopeResponse(**cached)

    # Try LLM generation
    from services.astro.llm_horoscope import (
        generate_daily_horoscope,
        generate_energy_scores_llm,
    )
    text = await generate_daily_horoscope(sign, date.today(), "today")
    if not text:
        text = _GENERIC_TEXTS.get(sign, _GENERIC_TEXTS["aries"])
    scores = await generate_energy_scores_llm(sign, date.today())

    response = HoroscopeResponse(
        sign=sign,
        sign_ru=_SIGN_RU.get(sign, sign),
        date=date.today(),
        period="today",
        text_ru=text,
        energy=EnergyScores(**scores),
        is_personalised=False,
    )
    await cache_set(cache_key, response.model_dump(mode="json"), settings.CACHE_TTL_HOROSCOPE)
    return response


@router.get("/period", response_model=HoroscopeResponse)
async def get_period_horoscope(
    period: str = Query(..., pattern="^(tomorrow|week|month)$"),
    sign: str | None = Query(None, description="Override sign (lowercase EN)"),
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Free endpoint. Returns the short tone-of-the-period text for all
    users. Premium subscribers may additionally see a detailed breakdown
    on the frontend; that detail call is gated separately when implemented.
    Accepts optional `sign` to view a generic horoscope for any sign."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    requested = (sign or "").lower().strip()
    if requested and requested in _VALID_SIGNS:
        sign = requested
    else:
        sign = user.sun_sign.value if user.sun_sign else "aries"
    today = date.today()

    # Check cache
    cache_key = key_horoscope(sign, today.isoformat(), period)
    cached = await cache_get(cache_key)
    if cached:
        return HoroscopeResponse(**cached)

    # Generate via LLM
    from services.astro.llm_horoscope import (
        generate_daily_horoscope,
        generate_energy_scores_llm,
    )
    text = await generate_daily_horoscope(sign, today, period)
    if not text:
        text = _GENERIC_TEXTS.get(sign, "")
    scores = await generate_energy_scores_llm(sign, today)

    response = HoroscopeResponse(
        sign=sign,
        sign_ru=_SIGN_RU.get(sign, sign),
        date=today,
        period=period,
        text_ru=text,
        energy=EnergyScores(**scores),
        is_personalised=bool(user.natal_chart),
    )
    await cache_set(cache_key, response.model_dump(mode="json"), settings.CACHE_TTL_HOROSCOPE)
    return response


@router.get("/moon", response_model=MoonPhaseResponse)
async def get_moon_today(tg_user: dict = Depends(get_tg_user)):
    """Current moon phase — free for all users."""
    today = date.today().isoformat()
    cache_key = key_moon(today)

    cached = await cache_get(cache_key)
    if cached:
        return MoonPhaseResponse(**cached)

    phase = get_moon_phase()
    response = MoonPhaseResponse(
        phase_name=phase.phase_name,
        phase_name_ru=phase.phase_name_ru,
        emoji=phase.emoji,
        description_ru=phase.description_ru,
        illumination=phase.illumination,
        date=phase.date,
        favorable_actions=phase.favorable_actions,
        avoid_actions=phase.avoid_actions,
    )
    await cache_set(cache_key, response.model_dump(mode="json"), settings.CACHE_TTL_MOON)
    return response


@router.get("/moon/calendar", response_model=MoonCalendarResponse)
async def get_moon_calendar(
    year: int = Query(default=None),
    month: int = Query(default=None),
    tg_user: dict = Depends(get_tg_user),
):
    """Monthly lunar calendar. Free."""
    now = datetime.now(UTC)
    y = year or now.year
    m = month or now.month

    cache_key = key_moon(f"{y}-{m:02d}")
    cached = await cache_get(cache_key)
    if cached:
        return MoonCalendarResponse(**cached)

    days_data = get_monthly_calendar(y, m)
    response = MoonCalendarResponse(
        year=y, month=m,
        days=[MoonCalendarDay(**d) for d in days_data],
    )
    await cache_set(cache_key, response.model_dump(mode="json"), settings.CACHE_TTL_MOON)
    return response


async def _personalised_horoscope(
    user, sign: str, today: str, period: str
) -> HoroscopeResponse:
    """Build a personalised horoscope via LLM, with transit fallback."""
    from services.astro.llm_horoscope import (
        generate_daily_horoscope,
        generate_energy_scores_llm,
    )

    # Check cache first
    cache_key = key_horoscope(sign, today, period)
    cached = await cache_get(cache_key)
    if cached:
        # Mark as personalised
        cached["is_personalised"] = True
        return HoroscopeResponse(**cached)

    # Generate via LLM
    text = await generate_daily_horoscope(sign, date.today(), period)
    if not text:
        text = _GENERIC_TEXTS.get(sign, _GENERIC_TEXTS["aries"])
    scores = await generate_energy_scores_llm(sign, date.today())

    response = HoroscopeResponse(
        sign=sign,
        sign_ru=_SIGN_RU.get(sign, sign),
        date=date.today(),
        period=period,
        text_ru=text,
        energy=EnergyScores(**scores),
        is_personalised=True,
    )
    await cache_set(cache_key, response.model_dump(mode="json"), settings.CACHE_TTL_HOROSCOPE)
    return response
