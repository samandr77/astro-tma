"""Transit endpoints — current planetary positions vs user's natal chart."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.transits import (
    EnergyScores,
    PeriodEvent,
    PeriodEventsResponse,
    RetrogradeInfo,
    SkyPosition,
    TransitAspect,
    TransitCategory,
    TransitDetailsRequest,
    TransitDetailsResponse,
    TransitsResponse,
)
from core.cache import cache_delete, cache_get, cache_set
from core.logging import get_logger
from core.settings import settings
from db.database import get_db
from services.astro.transit_interpreter import (
    get_or_generate_transit_texts,
    get_transit_details,
)
from services.astro.transits import (
    build_energy_scores,
    calculate_period_events,
    calculate_transits,
    get_current_sky,
)
from services.users import repository as user_repo

log = get_logger(__name__)
router = APIRouter(prefix="/transits", tags=["transits"])

from services.astro.planet_names import PLANET_RU as _PLANET_RU  # noqa: E402

_ASPECT_RU: dict[str, str] = {
    "conjunction": "Соединение", "opposition": "Оппозиция", "square": "Квадрат",
    "trine": "Трин", "sextile": "Секстиль",
}

_SIGN_RU: dict[str, str] = {
    "aries": "Овен", "taurus": "Телец", "gemini": "Близнецы",
    "cancer": "Рак", "leo": "Лев", "virgo": "Дева",
    "libra": "Весы", "scorpio": "Скорпион", "sagittarius": "Стрелец",
    "capricorn": "Козерог", "aquarius": "Водолей", "pisces": "Рыбы",
}

_SIGN_ABBR: dict[str, str] = {
    "Ari": "aries", "Tau": "taurus", "Gem": "gemini", "Can": "cancer",
    "Leo": "leo",   "Vir": "virgo",  "Lib": "libra",  "Sco": "scorpio",
    "Sag": "sagittarius", "Cap": "capricorn", "Aqu": "aquarius", "Pis": "pisces",
}

from services.astro.planet_names import PLANET_GLYPH as _PLANET_GLYPH  # noqa: E402

# Short, viral-friendly retrograde blurbs — written for a general audience.
_RETRO_BLURB: dict[str, str] = {
    "mercury": "Двойная проверка переписки и техники не повредит. Старые разговоры могут всплыть — есть шанс закрыть их по-новому.",
    "venus": "Старые чувства просыпаются: бывшие пишут, забытые вкусы возвращаются. Не торопитесь с новыми покупками и обещаниями.",
    "mars": "Дайте себе паузу: резкие решения и спор сейчас обходятся дороже. Лучше доделать начатое, чем рваться вперёд.",
    "jupiter": "Хорошее время сверить ориентиры — куда вы вообще идёте и что из старых планов ещё ваше. С большими шагами можно подождать.",
    "saturn": "Всё, что давно требовало внимания — обязательства, дисциплина, границы — даст о себе знать. Самое время навести порядок.",
    "uranus": "Внутри что-то меняется быстрее, чем снаружи. Можно неожиданно понять, что устарело, и без шума отпустить лишнее.",
    "neptune": "Мечтать и фантазировать — пожалуйста. А вот подписывать важное и верить на слово — лучше потом, когда туман рассеется.",
    "pluto": "Глубинные темы поднимаются: старые страхи, привязанности, контроль. Не бойтесь смотреть — это и есть взросление.",
}

_SUPPORT_PLANETS = {"venus", "jupiter"}
_TENSION_PLANETS = {"mars", "saturn"}
_TRANSFORMATION_PLANETS = {"pluto", "uranus", "neptune"}
_SOFT_ASPECTS = {"trine", "sextile"}
_HARD_ASPECTS = {"square", "opposition"}


def _classify_transit(transit_planet: str, natal_planet: str, aspect: str) -> TransitCategory:
    """Categorize transit per spec §6:
    - Transformation — any aspect with outer planets (Pluto/Uranus/Neptune)
    - Support — trine/sextile, OR conjunction with Venus/Jupiter
    - Tension — square/opposition with Mars/Saturn/Moon
    - Neutral — everything else
    """
    tp = transit_planet.lower()
    np = natal_planet.lower()
    ap = aspect.lower()

    if tp in _TRANSFORMATION_PLANETS or np in _TRANSFORMATION_PLANETS:
        return "transformation"

    if ap in _SOFT_ASPECTS:
        return "support"
    if ap == "conjunction" and (tp in _SUPPORT_PLANETS or np in _SUPPORT_PLANETS):
        return "support"

    if ap in _HARD_ASPECTS and (
        tp in _TENSION_PLANETS or np in _TENSION_PLANETS or tp == "moon" or np == "moon"
    ):
        return "tension"

    return "neutral"


_TRANSITS_TTL = 21600  # 6h — full response with all LLM texts populated
_TRANSITS_PARTIAL_TTL = 60  # 1 min — when LLM is still generating in background


def _key(user_id: int, d: str) -> str:
    return f"transits:{user_id}:{d}"


def _normalize_sign(raw: str) -> str:
    if not raw:
        return "unknown"
    if raw in _SIGN_ABBR:
        return _SIGN_ABBR[raw]
    return raw.lower()


async def _build_response(
    db: AsyncSession,
    raw_transits: list[dict],
    sign: str,
    response_date: date | None = None,
    *,
    cache_key_to_invalidate: str | None = None,
) -> tuple[TransitsResponse, int]:
    scores = build_energy_scores(raw_transits, sign)
    sky_raw = get_current_sky()

    # Per-pair interpretations — cached in transit_interpretations by
    # (transit_planet, natal_planet, aspect). On a cold cache we DON'T
    # block the response on the LLM call — that took 10-15s and reverse-
    # proxy timeouts made the first request fail. Instead we return with
    # the static fallback immediately and fill the cache in the background;
    # the next request (1 min Redis TTL) gets the real text.
    async def _invalidate() -> None:
        if cache_key_to_invalidate:
            await cache_delete(cache_key_to_invalidate)

    texts, missing_count = await get_or_generate_transit_texts(
        db,
        raw_transits,
        settings.ANTHROPIC_API_KEY,
        blocking=False,
        on_background_complete=_invalidate,
    )

    aspects = []
    for t in raw_transits:
        tp = t["transit_planet"].lower()
        np = t["natal_planet"].lower()
        ap = t["aspect"]
        aspects.append(
            TransitAspect(
                transit_planet=t["transit_planet"],
                natal_planet=t["natal_planet"],
                aspect=ap,
                orb=t["orb"],
                weight=t["weight"],
                transit_planet_ru=_PLANET_RU.get(tp, t["transit_planet"]),
                natal_planet_ru=_PLANET_RU.get(np, t["natal_planet"]),
                aspect_ru=_ASPECT_RU.get(ap, ap),
                transit_retrograde=t.get("transit_retrograde", False),
                applying=t.get("applying"),
                text_ru=texts.get((tp, np, ap)) or None,
                category=_classify_transit(tp, np, ap),
            )
        )

    sky: dict[str, SkyPosition] = {}
    retrogrades: list[RetrogradeInfo] = []
    for planet, data in sky_raw.items():
        s = _normalize_sign(data["sign"])
        sky[planet] = SkyPosition(
            sign=s,
            sign_ru=_SIGN_RU.get(s, s),
            degree=data["degree"],
            retrograde=data["retrograde"],
        )
        if data["retrograde"] and planet.lower() in _RETRO_BLURB:
            retrogrades.append(
                RetrogradeInfo(
                    planet=planet,
                    planet_ru=_PLANET_RU.get(planet.lower(), planet),
                    glyph=_PLANET_GLYPH.get(planet.lower(), "●"),
                    sign=s,
                    sign_ru=_SIGN_RU.get(s, s),
                    description_ru=_RETRO_BLURB[planet.lower()],
                )
            )

    return (
        TransitsResponse(
            date=response_date or date.today(),
            aspects=aspects,
            energy=EnergyScores(**scores),
            sky=sky,
            retrogrades=retrogrades,
        ),
        missing_count,
    )


@router.get("/current", response_model=TransitsResponse)
async def get_current_transits(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Current transits against user's natal chart + energy scores."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not user.natal_chart or not user.birth_date or not user.birth_tz:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No birth data — complete profile first",
        )

    today_str = date.today().isoformat()
    cache_key = _key(user.id, today_str)
    cached = await cache_get(cache_key)
    if cached:
        return TransitsResponse(**cached)

    raw_transits = calculate_transits(
        birth_dt=user.birth_date,
        lat=user.birth_lat or 0.0,
        lng=user.birth_lng or 0.0,
        tz_str=user.birth_tz,
        birth_time_known=user.birth_time_known,
    )

    sign = user.sun_sign.value if user.sun_sign else "aries"
    response, missing_count = await _build_response(
        db, raw_transits, sign, cache_key_to_invalidate=cache_key,
    )

    ttl = _TRANSITS_PARTIAL_TTL if missing_count > 0 else _TRANSITS_TTL
    await cache_set(cache_key, response.model_dump(mode="json"), ttl)
    return response


@router.get("/date", response_model=TransitsResponse)
async def get_transits_by_date(
    date_str: str = Query(..., alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Transits for arbitrary date (YYYY-MM-DD)."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not user.natal_chart or not user.birth_date or not user.birth_tz:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No birth data — complete profile first",
        )

    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid date format")

    cache_key = _key(user.id, date_str)
    cached = await cache_get(cache_key)
    if cached:
        return TransitsResponse(**cached)

    raw_transits = calculate_transits(
        birth_dt=user.birth_date,
        lat=user.birth_lat or 0.0,
        lng=user.birth_lng or 0.0,
        tz_str=user.birth_tz,
        birth_time_known=user.birth_time_known,
        dt=target,
    )

    sign = user.sun_sign.value if user.sun_sign else "aries"
    response, missing_count = await _build_response(
        db,
        raw_transits,
        sign,
        response_date=target.date(),
        cache_key_to_invalidate=cache_key,
    )

    ttl = _TRANSITS_PARTIAL_TTL if missing_count > 0 else _TRANSITS_TTL
    await cache_set(cache_key, response.model_dump(mode="json"), ttl)
    return response


@router.post("/details", response_model=TransitDetailsResponse)
async def get_transit_details_endpoint(
    payload: TransitDetailsRequest,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Deep-dive for the "What does this mean for me" CTA on the Transits hero.
    Returns the cached blurb plus practical do/avoid advice and the life-sphere
    (natal house) that the transit activates. Advice is lazy-generated and
    cached per (transit_planet, natal_planet, aspect) triple.
    """
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    from services.ratelimit import LIMITS, enforce_monthly_limit
    await enforce_monthly_limit(
        user.id, "transit_details", LIMITS["transit_details"],
        feature_ru="разборы транзитов",
    )

    chart = user.natal_chart.chart_data if user.natal_chart else None

    details = await get_transit_details(
        db,
        transit_planet=payload.transit_planet,
        natal_planet=payload.natal_planet,
        aspect=payload.aspect,
        natal_chart=chart,
        api_key=settings.ANTHROPIC_API_KEY,
    )
    return TransitDetailsResponse(**details)


_WEEK_TTL = 21600   # 6h
_MONTH_TTL = 43200  # 12h
_WEEK_TOP_N = 10
_MONTH_TOP_N = 20


def _ingress_title(planet_ru: str, sign_ru: str) -> str:
    return f"{planet_ru} входит в знак {sign_ru}"


def _aspect_title(transit_planet_ru: str, aspect_ru: str, natal_planet_ru: str) -> str:
    return f"{transit_planet_ru} {aspect_ru.lower()} {natal_planet_ru}"


async def _build_period_response(
    db: AsyncSession,
    raw_events: list[dict],
    start: date,
    end: date,
    *,
    cache_key_to_invalidate: str | None,
) -> tuple[PeriodEventsResponse, int]:
    """Turn a list of period-event dicts into the API response. Reuses the
    transit-interpretations cache for aspect text; ingresses get a static
    short description."""

    aspect_events = [e for e in raw_events if e["kind"] == "aspect"]

    async def _invalidate() -> None:
        if cache_key_to_invalidate:
            await cache_delete(cache_key_to_invalidate)

    texts, missing_count = await get_or_generate_transit_texts(
        db,
        aspect_events,
        settings.ANTHROPIC_API_KEY,
        blocking=False,
        on_background_complete=_invalidate,
    )

    events: list[PeriodEvent] = []
    for e in raw_events:
        if e["kind"] == "aspect":
            tp = e["transit_planet"].lower()
            np = e["natal_planet"].lower()
            ap = e["aspect"]
            tp_ru = _PLANET_RU.get(tp, e["transit_planet"])
            np_ru = _PLANET_RU.get(np, e["natal_planet"])
            ap_ru = _ASPECT_RU.get(ap, ap)
            events.append(
                PeriodEvent(
                    date=e["date"],
                    kind="aspect",
                    title_ru=_aspect_title(tp_ru, ap_ru, np_ru),
                    category=_classify_transit(tp, np, ap),
                    weight=e.get("weight", 0),
                    transit_planet=e["transit_planet"],
                    natal_planet=e["natal_planet"],
                    aspect=ap,
                    transit_planet_ru=tp_ru,
                    natal_planet_ru=np_ru,
                    aspect_ru=ap_ru,
                    orb=e.get("orb"),
                    text_ru=texts.get((tp, np, ap)) or None,
                )
            )
        elif e["kind"] == "ingress":
            planet = e["planet"]
            from_sign = _normalize_sign(e["from_sign"])
            to_sign = _normalize_sign(e["to_sign"])
            planet_ru = _PLANET_RU.get(planet.lower(), planet)
            to_sign_ru = _SIGN_RU.get(to_sign, to_sign)
            events.append(
                PeriodEvent(
                    date=e["date"],
                    kind="ingress",
                    title_ru=_ingress_title(planet_ru, to_sign_ru),
                    category="neutral",
                    weight=e.get("weight", 0),
                    planet=planet,
                    planet_ru=planet_ru,
                    from_sign=from_sign,
                    from_sign_ru=_SIGN_RU.get(from_sign, from_sign),
                    to_sign=to_sign,
                    to_sign_ru=to_sign_ru,
                )
            )

    return (
        PeriodEventsResponse(start_date=start, end_date=end, events=events),
        missing_count,
    )


@router.get("/week", response_model=PeriodEventsResponse)
async def get_week_events(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Top transit events for the next 7 days — Premium-only."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not await user_repo.is_premium(db, user.id):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Прогноз транзитов на неделю доступен только в Premium-подписке.",
        )
    if not user.natal_chart or not user.birth_date or not user.birth_tz:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No birth data — complete profile first",
        )

    start = date.today()
    end = start + timedelta(days=6)
    cache_key = f"transits-week:{user.id}:{start.isoformat()}"
    cached = await cache_get(cache_key)
    if cached:
        return PeriodEventsResponse(**cached)

    raw_events = calculate_period_events(
        birth_dt=user.birth_date,
        lat=user.birth_lat or 0.0,
        lng=user.birth_lng or 0.0,
        tz_str=user.birth_tz,
        start_date=start,
        days=7,
        birth_time_known=user.birth_time_known,
        top_n=_WEEK_TOP_N,
        include_moon_ingresses=False,
    )

    response, missing_count = await _build_period_response(
        db, raw_events, start, end, cache_key_to_invalidate=cache_key,
    )
    ttl = _TRANSITS_PARTIAL_TTL if missing_count > 0 else _WEEK_TTL
    await cache_set(cache_key, response.model_dump(mode="json"), ttl)
    return response


@router.get("/month", response_model=PeriodEventsResponse)
async def get_month_events(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Top transit events for the next 30 days — Premium-only."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not await user_repo.is_premium(db, user.id):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Прогноз транзитов на месяц доступен только в Premium-подписке.",
        )
    if not user.natal_chart or not user.birth_date or not user.birth_tz:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No birth data — complete profile first",
        )

    start = date.today()
    end = start + timedelta(days=29)
    cache_key = f"transits-month:{user.id}:{start.isoformat()}"
    cached = await cache_get(cache_key)
    if cached:
        return PeriodEventsResponse(**cached)

    raw_events = calculate_period_events(
        birth_dt=user.birth_date,
        lat=user.birth_lat or 0.0,
        lng=user.birth_lng or 0.0,
        tz_str=user.birth_tz,
        start_date=start,
        days=30,
        birth_time_known=user.birth_time_known,
        top_n=_MONTH_TOP_N,
        include_moon_ingresses=False,
    )

    response, missing_count = await _build_period_response(
        db, raw_events, start, end, cache_key_to_invalidate=cache_key,
    )
    ttl = _TRANSITS_PARTIAL_TTL if missing_count > 0 else _MONTH_TTL
    await cache_set(cache_key, response.model_dump(mode="json"), ttl)
    return response
