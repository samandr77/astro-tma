"""Destiny Matrix endpoints — calculate, fetch, look up an arcana, PDF."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from secrets import token_urlsafe
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.telegram_auth import get_tg_user
from api.schemas.destiny_matrix import (
    ArcanaResponse,
    DestinyMatrixPositions,
    DestinyMatrixResponse,
    InterpretationResponse,
)
from core.cache import cache_get, cache_set, key_destiny_pdf_download
from core.logging import get_logger
from core.settings import settings
from db.database import get_db
from db.models import (
    ArcanaMeaning,
    DestinyMatrixInterpretation,
    DestinyMatrixReading,
)
from services.destiny_matrix.arcana_names import (
    ARCANA_KEYWORDS_RU,
    CONTEXTS,
    GENERIC_DESC_RU,
    arcana_name,
)
from services.destiny_matrix.calculator import calculate_matrix
from services.destiny_matrix.interpreter import generate_interpretation
from services.destiny_matrix_pdf_html import generate_destiny_matrix_pdf_html
from services.users import repository as user_repo

router = APIRouter(prefix="/destiny-matrix", tags=["destiny-matrix"])
log = get_logger(__name__)
_PDF_DOWNLOAD_TTL_SECONDS = 300


async def _has_full_access(db: AsyncSession, user_id: int) -> bool:
    """Premium subscription OR a one-time destiny_matrix_full purchase."""
    is_prem = await user_repo.is_premium(db, user_id)
    if is_prem:
        return True
    return await user_repo.has_purchased(db, user_id, "destiny_matrix_full")


def _is_stale_positions(positions: dict) -> bool:
    """Detect old-format readings that need recompute. Staleness markers:
      (a) pre-ray-dots: channels.talents[0] equals personality.month (старый
          формат канала [corner, mid, end])
      (b) отсутствует блок `specials`, `money_diagonal`, `family_lines`
          (родовые линии добавлены вместе с новой формулой comfort)
      (c) `specials.love_diag_1` отсутствует — введён вместе с family_lines
    """
    if "specials" not in positions or "money_diagonal" not in positions:
        return True
    if "family_lines" not in positions:
        return True
    if "love_diag_1" not in positions.get("specials", {}):
        return True
    try:
        ch = positions["channels"]
        pers = positions["personality"]
        return ch["talents"][0] == pers["month"]
    except (KeyError, IndexError, TypeError):
        return True


async def _refresh_if_stale(
    db: AsyncSession, reading: DestinyMatrixReading, birth_date,
) -> None:
    """Recompute positions in place if stored in the old channel format,
    and drop the cached LLM interpretation (it was anchored to old numbers)."""
    if not _is_stale_positions(reading.positions):
        return
    reading.positions = calculate_matrix(birth_date)
    await db.execute(
        delete(DestinyMatrixInterpretation).where(
            DestinyMatrixInterpretation.reading_id == reading.id
        )
    )
    await db.flush()


@router.post("/calculate", response_model=DestinyMatrixResponse)
async def calculate(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Idempotent: returns the existing reading for the user's current
    birth_date or creates one. The matrix is pure-math, so the result
    is deterministic — same birth_date always yields the same numbers."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not user.birth_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Заполните дату рождения в профиле",
        )

    birth_date = user.birth_date.date() if isinstance(user.birth_date, datetime) else user.birth_date

    # Try existing reading first
    result = await db.execute(
        select(DestinyMatrixReading).where(
            DestinyMatrixReading.user_id == user.id,
            DestinyMatrixReading.birth_date == birth_date,
        )
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        positions = calculate_matrix(birth_date)
        reading = DestinyMatrixReading(
            user_id=user.id,
            birth_date=birth_date,
            positions=positions,
        )
        db.add(reading)
        try:
            await db.flush()
        except IntegrityError:
            # Concurrent insert from a duplicate /calculate — fetch the
            # winner. Same input → same positions, so it's fine.
            await db.rollback()
            result = await db.execute(
                select(DestinyMatrixReading).where(
                    DestinyMatrixReading.user_id == user.id,
                    DestinyMatrixReading.birth_date == birth_date,
                )
            )
            reading = result.scalar_one()
    else:
        await _refresh_if_stale(db, reading, birth_date)

    return DestinyMatrixResponse(
        positions=DestinyMatrixPositions.model_validate(reading.positions),
        birth_date=reading.birth_date,
        computed_at=reading.computed_at,
        has_full_access=await _has_full_access(db, user.id),
    )


@router.get("/me", response_model=DestinyMatrixResponse)
async def get_me(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the user's current matrix. Recomputes if birth_date has changed
    since the last reading (stale row gets ignored — a new row is added)."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not user.birth_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Заполните дату рождения в профиле",
        )

    birth_date = user.birth_date.date() if isinstance(user.birth_date, datetime) else user.birth_date

    result = await db.execute(
        select(DestinyMatrixReading).where(
            DestinyMatrixReading.user_id == user.id,
            DestinyMatrixReading.birth_date == birth_date,
        )
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        # First visit / birth_date changed — compute now.
        positions = calculate_matrix(birth_date)
        reading = DestinyMatrixReading(
            user_id=user.id,
            birth_date=birth_date,
            positions=positions,
        )
        db.add(reading)
        await db.flush()
    else:
        await _refresh_if_stale(db, reading, birth_date)

    return DestinyMatrixResponse(
        positions=DestinyMatrixPositions.model_validate(reading.positions),
        birth_date=reading.birth_date,
        computed_at=reading.computed_at,
        has_full_access=await _has_full_access(db, user.id),
    )


@router.get("/arcana/{num}", response_model=ArcanaResponse)
async def get_arcana(
    num: int,
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """All 8 context meanings for one arcana — used by the bottom-sheet.
    If a context row isn't in arcana_meanings yet (DB not seeded), returns
    GENERIC_DESC_RU as the meaning so the UI still shows something."""
    if not 1 <= num <= 22:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arcana num must be 1..22")

    _ = tg_user  # auth only — no per-user data leaves this endpoint

    rows = await db.execute(
        select(ArcanaMeaning).where(ArcanaMeaning.arcana_num == num)
    )
    by_ctx: dict[str, str] = {}
    name_db: str | None = None
    for row in rows.scalars():
        by_ctx[row.context] = row.meaning
        name_db = row.arcana_name

    contexts: dict[str, str] = {}
    for ctx in CONTEXTS:
        contexts[ctx] = by_ctx.get(ctx, GENERIC_DESC_RU)

    return ArcanaResponse(
        arcana_num=num,
        arcana_name=name_db or arcana_name(num),
        keywords=ARCANA_KEYWORDS_RU.get(num, []),
        contexts=contexts,
    )


# Free users get a 2-section preview; the rest is premium-gated.
FREE_SECTIONS: tuple[str, ...] = ("who_you_are", "karmic_tail")


def _mask_locked_sections(
    sections: dict[str, str], has_full_access: bool
) -> tuple[dict[str, str], list[str]]:
    """Return (visible_sections, locked_keys). Premium users see everything;
    free users see only the FREE_SECTIONS — the rest is replaced with a
    short teaser so the frontend can render a lock badge in place."""
    if has_full_access:
        return sections, []
    visible: dict[str, str] = {}
    locked: list[str] = []
    teaser = (
        "Эта секция доступна в полном разборе. Откройте, чтобы прочитать "
        "тёплый персональный анализ по вашим числам."
    )
    for key, text in sections.items():
        if key in FREE_SECTIONS:
            visible[key] = text
        else:
            visible[key] = teaser
            locked.append(key)
    return visible, locked


@router.get("/interpretation", response_model=InterpretationResponse)
async def get_interpretation(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM-generated 8-section personal narrative.

    V2: первые 2 секции (``who_you_are``, ``karmic_tail``) бесплатны;
    остальные 6 показываются только при полном доступе (Premium или
    одноразовая покупка ``destiny_matrix_full``). LLM-вызов выполняется
    один раз и кешируется per reading_id — премиум показывает уже
    сохранённый полный текст без повторной генерации."""
    user = await user_repo.get_by_id(db, tg_user["id"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    has_full_access = await _has_full_access(db, user.id)

    if not user.birth_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Заполните дату рождения в профиле",
        )

    birth_date = user.birth_date.date() if hasattr(user.birth_date, "date") else user.birth_date

    # Find the user's current reading (must exist — frontend always calls
    # /calculate before /interpretation).
    result = await db.execute(
        select(DestinyMatrixReading).where(
            DestinyMatrixReading.user_id == user.id,
            DestinyMatrixReading.birth_date == birth_date,
        )
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        # Edge case: race with /calculate. Build one now.
        positions = calculate_matrix(birth_date)
        reading = DestinyMatrixReading(
            user_id=user.id,
            birth_date=birth_date,
            positions=positions,
        )
        db.add(reading)
        await db.flush()
    else:
        await _refresh_if_stale(db, reading, birth_date)

    # Cached interpretation?
    cached_result = await db.execute(
        select(DestinyMatrixInterpretation).where(
            DestinyMatrixInterpretation.reading_id == reading.id,
        )
    )
    cached = cached_result.scalar_one_or_none()
    if cached:
        visible, locked = _mask_locked_sections(cached.sections, has_full_access)
        return InterpretationResponse(
            reading_id=reading.id,
            sections=visible,
            model=cached.model,
            generated_at=cached.generated_at,
            has_full_access=has_full_access,
            locked_sections=locked,
        )

    # First time — call LLM.
    sections, model = await generate_interpretation(
        positions=reading.positions,
        first_name=user.tg_first_name,
        api_key=settings.ANTHROPIC_API_KEY,
        gender=user.gender.value if user.gender else None,
    )

    # Don't cache the static fallback — that locks every future request
    # into the placeholder text. Return it once; the next visit retries
    # the LLM.
    if model == "fallback":
        log.warning("destiny_matrix.interp.fallback_no_cache", reading_id=reading.id)
        visible, locked = _mask_locked_sections(sections, has_full_access)
        return InterpretationResponse(
            reading_id=reading.id,
            sections=visible,
            model=model,
            generated_at=datetime.utcnow(),
            has_full_access=has_full_access,
            locked_sections=locked,
        )

    interp = DestinyMatrixInterpretation(
        reading_id=reading.id,
        sections=sections,
        model=model,
    )
    db.add(interp)
    try:
        await db.flush()
        await db.refresh(interp)
    except IntegrityError:
        # Lost a race with a parallel request — fetch the winner.
        await db.rollback()
        cached_result = await db.execute(
            select(DestinyMatrixInterpretation).where(
                DestinyMatrixInterpretation.reading_id == reading.id,
            )
        )
        interp = cached_result.scalar_one()

    visible, locked = _mask_locked_sections(interp.sections, has_full_access)
    return InterpretationResponse(
        reading_id=reading.id,
        sections=visible,
        model=interp.model,
        generated_at=interp.generated_at,
        has_full_access=has_full_access,
        locked_sections=locked,
    )


# ── PDF report ──────────────────────────────────────────────────────────────


def _destiny_pdf_filename(user) -> str:
    safe_name = str(user.tg_first_name or "matrix").replace('"', "").strip() or "matrix"
    return f"destiny_matrix_{safe_name}.pdf"


async def _get_pdf_user_or_error(db: AsyncSession, user_id: int):
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not await _has_full_access(db, user.id):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "PDF-отчёт доступен в Premium или после покупки полного разбора",
        )
    if not user.birth_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Заполните дату рождения в профиле",
        )
    return user


async def _get_or_create_pdf_reading(db: AsyncSession, user) -> DestinyMatrixReading:
    birth_date = (
        user.birth_date.date()
        if hasattr(user.birth_date, "date")
        else user.birth_date
    )
    result = await db.execute(
        select(DestinyMatrixReading).where(
            DestinyMatrixReading.user_id == user.id,
            DestinyMatrixReading.birth_date == birth_date,
        )
    )
    reading = result.scalar_one_or_none()
    if reading is None:
        reading = DestinyMatrixReading(
            user_id=user.id,
            birth_date=birth_date,
            positions=calculate_matrix(birth_date),
        )
        db.add(reading)
        await db.flush()
    else:
        await _refresh_if_stale(db, reading, birth_date)
    return reading


async def _get_or_generate_pdf_sections(
    db: AsyncSession, user, reading: DestinyMatrixReading
) -> dict[str, str]:
    """Use the cached LLM interpretation if it exists; otherwise generate one
    and cache it. The PDF is gated behind premium, so the LLM call is fine —
    a missed cache simply means a one-time ~3-5s wait."""
    cached_result = await db.execute(
        select(DestinyMatrixInterpretation).where(
            DestinyMatrixInterpretation.reading_id == reading.id,
        )
    )
    cached = cached_result.scalar_one_or_none()
    if cached:
        return cached.sections

    sections, model = await generate_interpretation(
        positions=reading.positions,
        first_name=user.tg_first_name,
        api_key=settings.ANTHROPIC_API_KEY,
        gender=user.gender.value if user.gender else None,
    )

    # Persist only real LLM output, never the static fallback (matches the
    # /interpretation endpoint policy).
    if model != "fallback":
        interp = DestinyMatrixInterpretation(
            reading_id=reading.id,
            sections=sections,
            model=model,
        )
        db.add(interp)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()

    return sections


async def _load_arcana_meanings(
    db: AsyncSession, gender: str | None
) -> dict[int, dict[str, dict[str, str | None]]]:
    """Return ``{arcana_num: {context: {meaning, plus, minus, professions}}}``
    prefering the reader's gender row and falling back to gender='any'."""
    rows = await db.execute(
        select(
            ArcanaMeaning.arcana_num,
            ArcanaMeaning.context,
            ArcanaMeaning.gender,
            ArcanaMeaning.meaning,
            ArcanaMeaning.plus,
            ArcanaMeaning.minus,
            ArcanaMeaning.professions,
        )
    )
    by_key: dict[tuple[int, str, str], dict[str, str | None]] = {}
    for r in rows.all():
        by_key[(r.arcana_num, r.context, r.gender)] = {
            "meaning": r.meaning,
            "plus": r.plus,
            "minus": r.minus,
            "professions": r.professions,
        }
    target_gender = gender if gender in ("male", "female") else None
    out: dict[int, dict[str, dict[str, str | None]]] = {}
    for (arc, ctx, g), fields in by_key.items():
        # Prefer the gender-specific row when present, fall back to 'any'.
        slot = out.setdefault(arc, {})
        existing = slot.get(ctx)
        if existing is None:
            slot[ctx] = fields
            slot[ctx]["_gender"] = g
            continue
        # An entry already exists — replace with the gendered one if relevant.
        if g == target_gender and existing.get("_gender") == "any":
            slot[ctx] = {**fields, "_gender": g}
    # Strip helper keys
    for ctx_map in out.values():
        for fields in ctx_map.values():
            fields.pop("_gender", None)
    return out


async def _build_destiny_pdf_bytes(db: AsyncSession, user) -> bytes:
    reading = await _get_or_create_pdf_reading(db, user)
    sections = await _get_or_generate_pdf_sections(db, user, reading)
    gender = user.gender.value if user.gender else None
    arcana_meanings = await _load_arcana_meanings(db, gender)
    return await generate_destiny_matrix_pdf_html(
        user_name=user.tg_first_name or "User",
        birth_date=str(reading.birth_date),
        positions=reading.positions,
        sections=sections,
        arcana_meanings=arcana_meanings,
        gender=gender,
    )


async def _build_destiny_pdf_response(db: AsyncSession, user) -> Response:
    try:
        pdf_bytes = await _build_destiny_pdf_bytes(db, user)
    except Exception as e:  # noqa: BLE001
        log.error("destiny_matrix.pdf_build_failed", user_id=user.id, error=str(e)[:500])
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Не удалось собрать PDF-отчёт. Попробуйте ещё раз.",
        ) from e
    filename = _destiny_pdf_filename(user)
    return Response(
        content=pdf_bytes,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f"attachment; filename=\"destiny-matrix.pdf\"; "
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _send_destiny_pdf_document(user, pdf_bytes: bytes) -> None:
    filename = _destiny_pdf_filename(user)
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendDocument"
    data = {
        "chat_id": str(user.id),
        "caption": "Ваш персональный PDF-разбор Матрицы Судьбы.",
    }
    files = {
        "document": (
            filename,
            BytesIO(pdf_bytes),
            "application/pdf",
        )
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)
        payload = response.json()
    except Exception as e:  # noqa: BLE001
        log.error("destiny_matrix.pdf_send_failed", user_id=user.id, error=str(e))
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Не удалось отправить PDF в Telegram. Попробуйте ещё раз.",
        ) from e

    if response.status_code == 403:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Сначала откройте чат с ботом и нажмите /start, затем попробуйте снова.",
        )

    if not response.is_success or not payload.get("ok"):
        description = str(payload.get("description") or response.text)
        log.error(
            "destiny_matrix.pdf_send_rejected",
            user_id=user.id,
            status_code=response.status_code,
            error=description[:500],
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Telegram не принял PDF. Попробуйте ещё раз.",
        )


@router.get("/pdf")
async def get_destiny_pdf(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return the Destiny Matrix PDF as a direct download."""
    user = await _get_pdf_user_or_error(db, tg_user["id"])
    return await _build_destiny_pdf_response(db, user)


@router.post("/pdf-link")
async def create_destiny_pdf_link(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a short-lived token URL for WebViews that block blob downloads."""
    user = await _get_pdf_user_or_error(db, tg_user["id"])
    token = token_urlsafe(24)
    await cache_set(
        key_destiny_pdf_download(token),
        {"user_id": user.id},
        _PDF_DOWNLOAD_TTL_SECONDS,
    )
    return {
        "download_url": f"/destiny-matrix/pdf-download/{token}",
        "filename": _destiny_pdf_filename(user),
        "expires_in": _PDF_DOWNLOAD_TTL_SECONDS,
    }


@router.post("/pdf-send")
async def send_destiny_pdf_to_telegram(
    tg_user: dict = Depends(get_tg_user),
    db: AsyncSession = Depends(get_db),
):
    """Build the PDF and deliver it to the user's Telegram chat as a document."""
    user = await _get_pdf_user_or_error(db, tg_user["id"])
    try:
        pdf_bytes = await _build_destiny_pdf_bytes(db, user)
    except Exception as e:  # noqa: BLE001
        log.error("destiny_matrix.pdf_build_failed", user_id=user.id, error=str(e)[:500])
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Не удалось собрать PDF-отчёт. Попробуйте ещё раз.",
        ) from e
    await _send_destiny_pdf_document(user, pdf_bytes)
    return {"status": "sent", "filename": _destiny_pdf_filename(user)}


@router.get("/pdf-download/{token}")
async def get_destiny_pdf_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Download the PDF via a short-lived token created by /pdf-link."""
    payload = await cache_get(key_destiny_pdf_download(token))
    if not isinstance(payload, dict) or "user_id" not in payload:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Download link expired")
    user = await _get_pdf_user_or_error(db, int(payload["user_id"]))
    return await _build_destiny_pdf_response(db, user)
