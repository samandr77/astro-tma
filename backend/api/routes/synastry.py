"""Synastry endpoints — invite-based compatibility flow between two users."""

import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.synastry import (
    SynastryAspectInterp,
    SynastryAspectOut,
    SynastryHistoryItem,
    SynastryHouseInfo,
    SynastryInviteInfo,
    SynastryManualInput,
    SynastryPending,
    SynastryPlanetInfo,
    SynastryRequestOut,
    SynastryResult,
    SynastryScores,
)
from core.logging import get_logger
from core.settings import settings
from db.database import get_db
from db.models import SynastryRequest, SynastryRequestStatus, User
from services.astro.synastry import calculate_synastry
from services.astro.synastry_interpreter import (
    generate_pair_summary,
    get_or_generate_aspect_texts,
)
from services.users import repository as user_repo

log = get_logger(__name__)
router = APIRouter(prefix="/synastry", tags=["synastry"])


async def _has_synastry_access(db, user_id: int) -> bool:
    """Premium subscription OR a one-off `synastry` purchase unlocks it."""
    if await user_repo.is_premium(db, user_id):
        return True
    return await user_repo.has_purchased(db, user_id, "synastry")

_TOKEN_TTL_DAYS = 7
_BOT_USERNAME_CACHE: str | None = None
_BOT_USERNAME_PLACEHOLDERS = {
    "",
    "astro_bot",
    "bot_username",
    "your_bot_username",
    "telegram_bot_username",
    "changeme",
}

from services.astro.planet_names import PLANET_RU as _PLANET_RU  # noqa: E402

_ASPECT_RU: dict[str, str] = {
    "conjunction": "Соединение", "opposition": "Оппозиция", "square": "Квадрат",
    "trine": "Трин", "sextile": "Секстиль",
}


def _clean_bot_username(value: str | None) -> str:
    return (value or "").strip().lstrip("@")


def _is_placeholder_bot_username(value: str) -> bool:
    return value.lower() in _BOT_USERNAME_PLACEHOLDERS


async def _resolve_bot_username() -> str:
    global _BOT_USERNAME_CACHE

    bot = (settings.TELEGRAM_BOT_USERNAME or "").strip().lstrip("@")
    if bot and not _is_placeholder_bot_username(bot):
        return bot

    if _BOT_USERNAME_CACHE:
        return _BOT_USERNAME_CACHE

    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "TELEGRAM_BOT_TOKEN не настроен",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as e:
        log.warning("synastry.bot_username_resolve_failed", error=str(e))
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Не удалось определить Telegram bot username",
        ) from e

    resolved = _clean_bot_username(payload.get("result", {}).get("username"))
    if not resolved:
        log.warning("synastry.bot_username_missing", payload_ok=payload.get("ok"))
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Telegram bot username не найден",
        )

    _BOT_USERNAME_CACHE = resolved
    return resolved


async def _invite_url(token: str) -> str:
    bot = await _resolve_bot_username()
    return f"https://t.me/{bot}?startapp=syn_{token}"


def _aspects_to_schema(raw: list[dict]) -> list[SynastryAspectOut]:
    return [
        SynastryAspectOut(
            p1_name=a["p1_name"],
            p2_name=a["p2_name"],
            p1_name_ru=_PLANET_RU.get(a["p1_name"].lower(), a["p1_name"]),
            p2_name_ru=_PLANET_RU.get(a["p2_name"].lower(), a["p2_name"]),
            aspect=a["aspect"],
            aspect_ru=_ASPECT_RU.get(a["aspect"], a["aspect"]),
            orb=a["orb"],
            weight=a["weight"],
        )
        for a in raw
    ]


def _coord_or_default(value: float | None) -> float:
    return value if value is not None else 0.0


def _is_valid_timezone(value: str | None) -> bool:
    if not value:
        return False
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return False
    return True


async def _resolve_synastry_timezone(
    tz: str | None,
    lat: float | None,
    lng: float | None,
) -> str:
    if _is_valid_timezone(tz):
        return str(tz)

    if lat is not None and lng is not None:
        from api.routes.users import _get_timezone  # late import to avoid cycles

        resolved = await _get_timezone(lat, lng)
        if _is_valid_timezone(resolved):
            return resolved

    return "UTC"


def _synastry_user_payload(user: User, tz: str) -> dict:
    return {
        "name": user.tg_first_name,
        "birth_dt": user.birth_date,
        "lat": _coord_or_default(user.birth_lat),
        "lng": _coord_or_default(user.birth_lng),
        "tz_str": tz,
        "birth_time_known": user.birth_time_known,
    }


async def _require_user_with_chart(db: AsyncSession, user_id: int) -> User:
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not user.natal_chart or not user.birth_date or not user.birth_tz:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Заполните данные рождения в профиле",
        )
    return user


def _planets_from_chart(chart_data: dict) -> list[SynastryPlanetInfo]:
    """Project NatalChart.chart_data['planets'] dict into the response schema."""
    raw = chart_data.get("planets") if chart_data else None
    if not isinstance(raw, dict):
        return []
    out: list[SynastryPlanetInfo] = []
    for name, p in raw.items():
        if not isinstance(p, dict):
            continue
        name_key = str(name or "")
        out.append(
            SynastryPlanetInfo(
                name=name_key,
                name_ru=_PLANET_RU.get(name_key, name_key),
                sign=str(p.get("sign", "")),
                sign_ru=str(p.get("sign_ru") or p.get("sign", "")),
                degree=float(p.get("degree", 0) or 0),
                sign_degree=float(p.get("sign_degree", p.get("degree", 0)) or 0),
                house=int(p.get("house", 0) or 0),
                retrograde=bool(p.get("retrograde", False)),
            )
        )
    return out


def _houses_from_chart(chart_data: dict) -> list[SynastryHouseInfo]:
    raw = chart_data.get("houses") if chart_data else None
    if not isinstance(raw, list):
        return []
    out: list[SynastryHouseInfo] = []
    for h in raw:
        if not isinstance(h, dict):
            continue
        out.append(
            SynastryHouseInfo(
                number=int(h.get("number", 0) or 0),
                sign=str(h.get("sign", "")),
                sign_ru=str(h.get("sign_ru") or h.get("sign", "")),
                degree=float(h.get("degree", 0) or 0),
            )
        )
    return out


def _interp_to_schema(
    aspects: list[dict],
    texts: dict[tuple[str, str, str], str],
) -> list[SynastryAspectInterp]:
    """Pair each aspect with its cached/generated Russian text.
    Skips aspects with empty text so we don't render blank cards."""
    out: list[SynastryAspectInterp] = []
    for a in aspects:
        p1l, p2l = a["p1_name"].lower(), a["p2_name"].lower()
        key_a, key_b = (p1l, p2l) if p1l <= p2l else (p2l, p1l)
        text = texts.get((key_a, key_b, a["aspect"]), "")
        if not text:
            continue
        out.append(
            SynastryAspectInterp(
                p1_name=a["p1_name"],
                p2_name=a["p2_name"],
                p1_name_ru=_PLANET_RU.get(p1l, a["p1_name"]),
                p2_name_ru=_PLANET_RU.get(p2l, a["p2_name"]),
                aspect=a["aspect"],
                aspect_ru=_ASPECT_RU.get(a["aspect"], a["aspect"]),
                orb=float(a["orb"]),
                text_ru=text,
            )
        )
    return out


@router.post("/request", response_model=SynastryRequestOut)
async def create_request(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate (or reuse) an invite token for synastry. Requires prior synastry purchase."""
    user = await _require_user_with_chart(db, tg_user["id"])

    if not await _has_synastry_access(db, user.id):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Покупка Синастрии обязательна")

    now = datetime.now(UTC)

    result = await db.execute(
        select(SynastryRequest)
        .where(
            SynastryRequest.initiator_user_id == user.id,
            SynastryRequest.status == SynastryRequestStatus.PENDING,
            SynastryRequest.expires_at > now,
        )
        .order_by(SynastryRequest.created_at.desc())
    )
    req = result.scalars().first()

    if req is None:
        req = SynastryRequest(
            initiator_user_id=user.id,
            token=secrets.token_urlsafe(12),
            status=SynastryRequestStatus.PENDING,
            expires_at=now + timedelta(days=_TOKEN_TTL_DAYS),
        )
        db.add(req)
        await db.flush()
        log.info("synastry.request_created", user_id=user.id, token=req.token)

    await db.commit()

    return SynastryRequestOut(
        id=req.id,
        token=req.token,
        invite_url=await _invite_url(req.token),
        status=req.status.value,
        expires_at=req.expires_at,
        initiator_name=user.tg_first_name,
    )


@router.get("/pending", response_model=list[SynastryPending])
async def get_pending(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Inbound pending invitations where current user is the partner."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(SynastryRequest, User)
        .join(User, User.id == SynastryRequest.initiator_user_id)
        .where(
            SynastryRequest.partner_user_id == tg_user["id"],
            SynastryRequest.status == SynastryRequestStatus.PENDING,
            SynastryRequest.expires_at > now,
        )
    )
    out = []
    for req, initiator in result.all():
        out.append(SynastryPending(
            id=req.id,
            token=req.token,
            initiator_name=initiator.tg_first_name,
            expires_at=req.expires_at,
        ))
    return out


@router.get("/invite/{token}", response_model=SynastryInviteInfo)
async def get_invite_info(
    token: str,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Lookup invite by token without requiring a chart. Used by the link
    landing page to greet the recipient with the initiator's name even
    before they've finished onboarding."""
    result = await db.execute(
        select(SynastryRequest, User)
        .join(User, User.id == SynastryRequest.initiator_user_id)
        .where(SynastryRequest.token == token)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приглашение не найдено")
    req, initiator = row
    now = datetime.now(UTC)
    return SynastryInviteInfo(
        initiator_name=initiator.tg_first_name,
        status=req.status.value,
        expires_at=req.expires_at,
        is_own=(req.initiator_user_id == tg_user["id"]),
        is_expired=req.expires_at <= now,
    )


@router.post("/accept/{token}", response_model=SynastryResult)
async def accept_request(
    token: str,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Partner accepts the invitation. Both users must have natal charts."""
    partner = await _require_user_with_chart(db, tg_user["id"])
    partner_chart = partner.natal_chart
    if partner_chart is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Заполните данные рождения в профиле")

    now = datetime.now(UTC)
    result = await db.execute(
        select(SynastryRequest).where(SynastryRequest.token == token)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Приглашение не найдено")

    if req.initiator_user_id == partner.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя принять собственное приглашение")

    if req.expires_at <= now:
        req.status = SynastryRequestStatus.EXPIRED
        await db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Срок действия приглашения истёк")

    if req.status == SynastryRequestStatus.COMPLETED and req.result_json:
        initiator = await user_repo.get_by_id(db, req.initiator_user_id)
        data = req.result_json
        # Re-fetch interpretations from cache (cheap) — text bodies are not
        # stored in result_json so the table can be regenerated/edited later.
        texts = await get_or_generate_aspect_texts(
            db, data["aspects"], settings.ANTHROPIC_API_KEY
        )
        return SynastryResult(
            id=req.id,
            aspects=_aspects_to_schema(data["aspects"]),
            scores=SynastryScores(**data["scores"]),
            total_aspects=data["total_aspects"],
            initiator_name=initiator.tg_first_name if initiator else None,
            partner_name=partner.tg_first_name,
            is_initiator=False,
            planets_a=_planets_from_chart(initiator.natal_chart.chart_data) if initiator and initiator.natal_chart else [],
            planets_b=_planets_from_chart(partner.natal_chart.chart_data) if partner.natal_chart else [],
            houses_a=_houses_from_chart(initiator.natal_chart.chart_data) if initiator and initiator.natal_chart else [],
            houses_b=_houses_from_chart(partner.natal_chart.chart_data) if partner.natal_chart else [],
            interpretations=_interp_to_schema(data["aspects"], texts),
            summary_ru=data.get("summary_ru"),
            created_at=req.created_at,
        )

    initiator = await _require_user_with_chart(db, req.initiator_user_id)
    initiator_chart = initiator.natal_chart
    if initiator_chart is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Заполните данные рождения в профиле")

    from services.ratelimit import LIMITS, enforce_monthly_limit
    await enforce_monthly_limit(
        partner.id, "synastry_calc", LIMITS["synastry_calc"], feature_ru="расчёты синастрии",
    )

    initiator_tz = await _resolve_synastry_timezone(
        initiator.birth_tz,
        initiator.birth_lat,
        initiator.birth_lng,
    )
    partner_tz = await _resolve_synastry_timezone(
        partner.birth_tz,
        partner.birth_lat,
        partner.birth_lng,
    )

    try:
        raw = calculate_synastry(
            user_a=_synastry_user_payload(initiator, initiator_tz),
            user_b=_synastry_user_payload(partner, partner_tz),
        )
    except Exception as exc:
        log.exception(
            "synastry.accept_calculation_failed",
            request_id=req.id,
            initiator=initiator.id,
            partner=partner.id,
            error=str(exc),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Не удалось рассчитать совместимость. Проверьте данные рождения в профиле.",
        ) from exc

    # Aspect texts and pair summary are both cached now — aspect texts by
    # (p1,p2,aspect) triple, summary by deterministic hash of inputs. Same
    # pair recomputed twice yields the same prose.
    texts = await get_or_generate_aspect_texts(
        db, raw["aspects"], settings.ANTHROPIC_API_KEY
    )
    summary = await generate_pair_summary(
        db,
        initiator.tg_first_name,
        partner.tg_first_name,
        raw["aspects"],
        raw["scores"],
        settings.ANTHROPIC_API_KEY,
    )

    req.partner_user_id = partner.id
    req.status = SynastryRequestStatus.COMPLETED
    req.result_json = {**raw, "summary_ru": summary}
    await db.commit()
    log.info("synastry.completed", request_id=req.id, initiator=initiator.id, partner=partner.id)

    return SynastryResult(
        id=req.id,
        aspects=_aspects_to_schema(raw["aspects"]),
        scores=SynastryScores(**raw["scores"]),
        total_aspects=raw["total_aspects"],
        initiator_name=initiator.tg_first_name,
        partner_name=partner.tg_first_name,
        is_initiator=False,
        planets_a=_planets_from_chart(initiator_chart.chart_data),
        planets_b=_planets_from_chart(partner_chart.chart_data),
        houses_a=_houses_from_chart(initiator_chart.chart_data),
        houses_b=_houses_from_chart(partner_chart.chart_data),
        interpretations=_interp_to_schema(raw["aspects"], texts),
        summary_ru=summary,
        created_at=req.created_at,
    )


@router.post("/manual", response_model=SynastryResult)
async def manual_synastry(
    payload: SynastryManualInput,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute synastry between the current user and a manually-entered partner.
    The partner isn't a Telegram user, so we calculate their natal chart
    on the fly and stash it inside the persisted SynastryRequest.result_json
    (no User / NatalChart row). The full report — planets, interpretations,
    summary — is returned and the row shows up in the user's history just
    like an invite-flow synastry.
    """
    from services.astro.natal import calculate_natal, chart_to_json

    initiator = await _require_user_with_chart(db, tg_user["id"])
    initiator_chart = initiator.natal_chart
    if initiator_chart is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Заполните данные рождения в профиле")

    if not await _has_synastry_access(db, initiator.id):
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Покупка Синастрии обязательна")

    from services.ratelimit import LIMITS, enforce_monthly_limit
    await enforce_monthly_limit(
        initiator.id, "synastry_calc", LIMITS["synastry_calc"], feature_ru="расчёты синастрии",
    )

    # Combine birth_date + birth_time into a single datetime
    try:
        hh, mm = payload.birth_time.split(":", 1)
        partner_dt = datetime(
            payload.birth_date.year,
            payload.birth_date.month,
            payload.birth_date.day,
            int(hh),
            int(mm),
        )
    except (ValueError, IndexError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Некорректный формат времени рождения (ожидается HH:MM)",
        ) from exc

    # Resolve partner coordinates from city if not provided by the client.
    partner_lat = payload.birth_lat
    partner_lng = payload.birth_lng
    partner_city = payload.birth_city
    if partner_lat is None or partner_lng is None:
        from api.routes.users import _geocode_city  # late import to avoid cycles
        geo = await _geocode_city(payload.birth_city)
        partner_lat = geo["lat"]
        partner_lng = geo["lng"]
        partner_city = geo.get("city") or partner_city

    initiator_tz = await _resolve_synastry_timezone(
        initiator.birth_tz,
        initiator.birth_lat,
        initiator.birth_lng,
    )
    partner_tz = await _resolve_synastry_timezone(
        payload.birth_tz,
        partner_lat,
        partner_lng,
    )

    try:
        raw = calculate_synastry(
            user_a=_synastry_user_payload(initiator, initiator_tz),
            user_b={
                "name": payload.partner_name,
                "birth_dt": partner_dt,
                "lat": partner_lat,
                "lng": partner_lng,
                "tz_str": partner_tz,
                "birth_time_known": payload.birth_time_known,
            },
        )
    except Exception as exc:
        log.exception(
            "synastry.manual_calculation_failed",
            initiator_id=initiator.id,
            partner_name=payload.partner_name,
            partner_city=partner_city,
            error=str(exc),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Не удалось рассчитать совместимость. Проверьте дату, время и город рождения.",
        ) from exc

    # Build partner's natal chart data so the report can render their planet
    # table and the bi-wheel's outer ring. Failure here just means the report
    # falls back to "no chart data for partner" — the synastry numbers above
    # are still valid.
    partner_chart_data: dict | None = None
    try:
        partner_chart = calculate_natal(
            name=payload.partner_name,
            birth_dt=partner_dt,
            lat=partner_lat,
            lng=partner_lng,
            tz_str=partner_tz,
            birth_time_known=payload.birth_time_known,
        )
        partner_chart_data = chart_to_json(partner_chart)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "synastry.manual_partner_chart_failed",
            initiator_id=initiator.id,
            partner_name=payload.partner_name,
            error=str(exc),
        )

    # Aspect texts and pair summary — both cached by (p1,p2,aspect) /
    # input-hash respectively. Same partner data → same texts.
    texts = await get_or_generate_aspect_texts(
        db, raw["aspects"], settings.ANTHROPIC_API_KEY
    )
    summary = await generate_pair_summary(
        db,
        initiator.tg_first_name,
        payload.partner_name,
        raw["aspects"],
        raw["scores"],
        settings.ANTHROPIC_API_KEY,
    )

    # Persist as a SynastryRequest with no partner_user_id — this is the
    # marker for "manual entry". result_json carries everything the report
    # needs: aspects, scores, summary, partner name and partner chart data.
    req = SynastryRequest(
        initiator_user_id=initiator.id,
        partner_user_id=None,
        token=f"m_{secrets.token_urlsafe(10)}",
        status=SynastryRequestStatus.COMPLETED,
        result_json={
            **raw,
            "summary_ru": summary,
            "partner_name": payload.partner_name,
            "partner_chart_data": partner_chart_data,
            "manual": True,
        },
        expires_at=datetime.now(UTC) + timedelta(days=365 * 5),
    )
    db.add(req)
    await db.flush()
    await db.commit()

    log.info(
        "synastry.manual_completed",
        initiator_id=initiator.id,
        request_id=req.id,
        partner_name=payload.partner_name,
        partner_city=partner_city,
        total=raw["total_aspects"],
    )

    return SynastryResult(
        id=req.id,
        aspects=_aspects_to_schema(raw["aspects"]),
        scores=SynastryScores(**raw["scores"]),
        total_aspects=raw["total_aspects"],
        initiator_name=initiator.tg_first_name,
        partner_name=payload.partner_name,
        is_initiator=True,
        planets_a=_planets_from_chart(initiator_chart.chart_data),
        planets_b=_planets_from_chart(partner_chart_data) if partner_chart_data else [],
        houses_a=_houses_from_chart(initiator_chart.chart_data),
        houses_b=_houses_from_chart(partner_chart_data) if partner_chart_data else [],
        interpretations=_interp_to_schema(raw["aspects"], texts),
        summary_ru=summary,
        created_at=req.created_at,
    )


@router.get("/result/{request_id}", response_model=SynastryResult)
async def get_result(
    request_id: int,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the full synastry result — accessible to both initiator and partner.
    Returns the same shape as accept_request, including planets, interpretations
    and the pair summary, so the same SynastryReport component renders it."""
    user_id = tg_user["id"]
    result = await db.execute(
        select(SynastryRequest).where(SynastryRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Результат не найден")

    if user_id not in (req.initiator_user_id, req.partner_user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа")

    if req.status != SynastryRequestStatus.COMPLETED or not req.result_json:
        raise HTTPException(status.HTTP_409_CONFLICT, "Расчёт ещё не готов")

    is_initiator = user_id == req.initiator_user_id
    initiator = await user_repo.get_by_id(db, req.initiator_user_id)
    partner = (
        await user_repo.get_by_id(db, req.partner_user_id)
        if req.partner_user_id
        else None
    )
    data = req.result_json

    # Manual entries: partner has no User row; their natal-chart-shaped data
    # was stashed in result_json at create time, and the name comes from
    # there too.
    partner_name: str | None = None
    partner_chart_data: dict | None = None
    if partner is not None:
        partner_name = partner.tg_first_name
        partner_chart_data = partner.natal_chart.chart_data if partner.natal_chart else None
    else:
        partner_name = data.get("partner_name")
        partner_chart_data = data.get("partner_chart_data")

    texts = await get_or_generate_aspect_texts(
        db, data["aspects"], settings.ANTHROPIC_API_KEY
    )

    return SynastryResult(
        id=req.id,
        aspects=_aspects_to_schema(data["aspects"]),
        scores=SynastryScores(**data["scores"]),
        total_aspects=data["total_aspects"],
        initiator_name=initiator.tg_first_name if initiator else None,
        partner_name=partner_name,
        is_initiator=is_initiator,
        planets_a=_planets_from_chart(initiator.natal_chart.chart_data)
        if initiator and initiator.natal_chart
        else [],
        planets_b=_planets_from_chart(partner_chart_data) if partner_chart_data else [],
        houses_a=_houses_from_chart(initiator.natal_chart.chart_data)
        if initiator and initiator.natal_chart
        else [],
        houses_b=_houses_from_chart(partner_chart_data) if partner_chart_data else [],
        interpretations=_interp_to_schema(data["aspects"], texts),
        summary_ru=data.get("summary_ru"),
        created_at=req.created_at,
    )


@router.get("/history", response_model=list[SynastryHistoryItem])
async def get_history(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Past completed synastries the user participated in (as either side),
    sorted newest first. Hidden flags filter by the viewer's perspective."""
    user_id = tg_user["id"]

    result = await db.execute(
        select(SynastryRequest)
        .where(
            SynastryRequest.status == SynastryRequestStatus.COMPLETED,
            SynastryRequest.result_json.is_not(None),
            or_(
                and_(
                    SynastryRequest.initiator_user_id == user_id,
                    SynastryRequest.hidden_by_initiator.is_(False),
                ),
                and_(
                    SynastryRequest.partner_user_id == user_id,
                    SynastryRequest.hidden_by_partner.is_(False),
                ),
            ),
        )
        .order_by(SynastryRequest.created_at.desc())
    )
    rows = result.scalars().all()
    if not rows:
        return []

    # Resolve the OTHER party's display name in one pass
    counterpart_ids = {
        (req.partner_user_id if req.initiator_user_id == user_id else req.initiator_user_id)
        for req in rows
    }
    counterpart_ids.discard(None)
    name_lookup: dict[int, str | None] = {}
    if counterpart_ids:
        users = await db.execute(
            select(User.id, User.tg_first_name).where(User.id.in_(counterpart_ids))
        )
        name_lookup = {u_id: name for u_id, name in users.all()}

    out: list[SynastryHistoryItem] = []
    for req in rows:
        is_initiator = req.initiator_user_id == user_id
        counterpart_id = req.partner_user_id if is_initiator else req.initiator_user_id
        partner_name = name_lookup.get(counterpart_id) if counterpart_id else None
        data = req.result_json or {}
        # Manual entries store the partner name directly in result_json
        # (no User row to look up).
        if not partner_name:
            partner_name = data.get("partner_name")
        scores = SynastryScores(**data.get("scores", {
            "love": 0, "communication": 0, "trust": 0, "passion": 0, "overall": 0,
        }))
        out.append(
            SynastryHistoryItem(
                id=req.id,
                partner_name=partner_name,
                is_initiator=is_initiator,
                scores=scores,
                total_aspects=int(data.get("total_aspects", 0)),
                created_at=req.created_at,
            )
        )
    return out


@router.delete("/history/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hide_from_history(
    request_id: int,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete from the current user's history. The other side keeps it.
    Once both sides have hidden the row, drop it entirely."""
    user_id = tg_user["id"]
    result = await db.execute(
        select(SynastryRequest).where(SynastryRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запись не найдена")

    if user_id == req.initiator_user_id:
        req.hidden_by_initiator = True
    elif user_id == req.partner_user_id:
        req.hidden_by_partner = True
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа")

    if req.hidden_by_initiator and req.hidden_by_partner:
        await db.delete(req)

    await db.commit()
    return None
