"""Telegram Bot API push notifications."""

import hashlib
import re
from datetime import date

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.settings import settings
from db.models import (
    NotificationLog,
    NotificationStatus,
    NotificationType,
    User,
)

log = get_logger(__name__)
# Phrased as a direct invitation to *finish* an interrupted message —
# matches the cliff-hanger ellipsis at the end of the push body.
DAILY_OPEN_APP_LABEL = "✦ Дочитать в приложении"

_MONTHS_RU = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

_GREETINGS = (
    "Доброе утро, {name}.",
    "{name}, доброе утро.",
    "С новым утром, {name}.",
    "{name}, пусть утро начнется мягко.",
    "Доброе утро, {name}: сегодня важно услышать себя.",
    "{name}, утро уже подсказывает направление.",
)

_INTROS = (
    "Астрологический акцент на {day} для знака {sign}:",
    "Гороскоп для знака {sign} на {day}:",
    "Сегодняшний настрой для знака {sign} на {day}:",
    "Что стоит взять с собой в этот день: знак {sign}, {day}:",
    "Космическая заметка для знака {sign} на {day}:",
    "Главный тон дня для знака {sign} на {day}:",
)

_BRIDGES = (
    "Обратите внимание на главное:",
    "Коротко о том, как прожить день внимательнее:",
    "Вот что может стать полезным ориентиром:",
    "Сегодня лучше держать в фокусе это:",
    "Для более спокойного ритма дня:",
    "Пусть это будет вашей точкой опоры:",
)

_CLOSINGS = (
    "Пусть день сложится без лишней спешки.",
    "Берегите темп и выбирайте то, что действительно важно.",
    "Дайте себе немного пространства перед важными решениями.",
    "Пусть сегодня будет больше ясности, чем шума.",
    "Сделайте один точный шаг, а остальное выстроится легче.",
    "Не торопите события: день лучше раскрывается постепенно.",
)

# Tease, don't conclude — every pattern ends with `{teaser}` so the
# message visually breaks off mid-thought. The CTA button "Читать далее"
# is the only natural way for the user to finish reading.
_MESSAGE_PATTERNS = (
    "{greeting}\n{intro}\n\n{teaser}",
    "{greeting}\n\n{intro}\n{teaser}",
    "{greeting}\n{intro}\n\n{bridge}\n{teaser}",
    "{greeting}\n{intro}\n{bridge_lc}\n{teaser}",
    "{greeting}\n\n{intro}\n\n{bridge}\n{teaser}",
)

_SENTENCE_RE = re.compile(r"[^.!?…]+[.!?…]+", re.MULTILINE)
_SAFE_CUT_RE = re.compile(r"^(.{120,360}?)[,;:—-]\s+\S*$", re.DOTALL)


async def send_message(
    db: AsyncSession,
    user: User,
    text: str,
    type_: NotificationType = NotificationType.DAILY_HOROSCOPE,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    """
    Send a message via Telegram Bot API. Logs result to NotificationLog.
    On 403 (user blocked bot) → sets user.push_enabled=False.
    Returns True if sent successfully.

    `reply_markup` — optional Telegram reply_markup dict, e.g. an
    inline_keyboard with a `web_app` button to deep-link into the Mini App.
    """
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict = {
        "chat_id": user.id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        data = resp.json()
    except Exception as e:
        db.add(NotificationLog(
            user_id=user.id, type=type_,
            status=NotificationStatus.FAILED, error=str(e)[:500],
        ))
        await db.flush()
        log.error("push.network_error", user_id=user.id, error=str(e))
        return False

    if data.get("ok"):
        msg_id = data.get("result", {}).get("message_id")
        db.add(NotificationLog(
            user_id=user.id, type=type_,
            status=NotificationStatus.SENT, tg_message_id=msg_id,
        ))
        await db.flush()
        log.info("push.sent", user_id=user.id, message_id=msg_id)
        return True

    # Not ok
    err_code = data.get("error_code")
    description = data.get("description", "")
    if err_code == 403:
        user.push_enabled = False
        log.warning("push.blocked_by_user", user_id=user.id)

    db.add(NotificationLog(
        user_id=user.id, type=type_,
        status=NotificationStatus.FAILED,
        error=f"{err_code}: {description}"[:500],
    ))
    await db.flush()
    log.error("push.failed", user_id=user.id, code=err_code, description=description)
    return False


def _daily_variant(user_id: int, sign_ru: str, target_date: date) -> int:
    seed = f"{user_id}:{sign_ru}:{target_date.isoformat()}".encode()
    return int(hashlib.blake2s(seed, digest_size=4).hexdigest(), 16)


def _pick(options: tuple[str, ...], variant: int, salt: int) -> str:
    return options[(variant >> salt) % len(options)]


def _format_ru_date(target_date: date) -> str:
    return f"{target_date.day} {_MONTHS_RU[target_date.month - 1]}"


def _ensure_final_period(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    text = text.rstrip("…").rstrip()
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _normalize_horoscope_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text.replace("...", "…")


_CLIFFHANGER_TRIM = ".,!?;:—-– \t\n«»\"'"


def _cliffhanger_cut(text: str, *, target_chars: int) -> str:
    """Trim `text` to roughly `target_chars`, snap back to the previous
    word boundary, strip any dangling punctuation, and append `…`."""
    if not text:
        return ""
    cut = text[:target_chars]
    last_space = cut.rfind(" ")
    if last_space > target_chars * 0.5:
        cut = cut[:last_space]
    cut = cut.rstrip(_CLIFFHANGER_TRIM)
    if not cut:
        return ""
    return f"{cut}…"


def _sentence_teaser(text: str, *, target_chars: int = 240) -> str:
    """Cliff-hanger teaser: cut the daily horoscope mid-sentence so the
    push reads like a story that breaks off — pushing the user to tap
    "Читать далее" to finish it inside the app.

    Strategy: keep 1-2 full sentences if they fit comfortably, then cut
    the next sentence mid-word and append `…`. Never end on a full stop.
    """
    normalized = _normalize_horoscope_text(text)
    if not normalized:
        return "Сегодня есть на что обратить внимание — подробности уже ждут вас…"

    sentences = [match.group(0).strip() for match in _SENTENCE_RE.finditer(normalized)]
    if not sentences:
        return _cliffhanger_cut(normalized, target_chars=target_chars)

    # Keep whole sentences until we're close to the target, then chip a
    # piece of the next one so the message ends in the middle.
    kept: list[str] = []
    total = 0
    cut_next: str | None = None
    for sentence in sentences:
        sentence = sentence.strip()
        projected = total + len(sentence) + (1 if kept else 0)
        if projected <= target_chars - 20:
            kept.append(sentence)
            total = projected
            continue
        # The next sentence won't fit whole — keep a fragment of it.
        remaining = max(40, target_chars - total - 2)
        cut_next = _cliffhanger_cut(sentence, target_chars=remaining)
        break

    if cut_next:
        prefix = " ".join(kept).strip()
        return (f"{prefix} {cut_next}" if prefix else cut_next).strip()

    # Everything fit — still drop the final period so it feels open-ended.
    joined = " ".join(kept).strip()
    return _cliffhanger_cut(joined, target_chars=target_chars) or joined


def build_daily_message(
    user: User,
    sign_ru: str,
    text_ru: str,
    energy: dict,
    *,
    message_date: date | None = None,
) -> str:
    """Compose a short daily horoscope push."""
    name = user.tg_first_name or "друг"
    target_date = message_date or date.today()
    variant = _daily_variant(user.id, sign_ru, target_date)
    day = _format_ru_date(target_date)
    teaser = _sentence_teaser(text_ru)
    greeting = _pick(_GREETINGS, variant, 0).format(name=name)
    intro = _pick(_INTROS, variant, 5).format(sign=sign_ru, day=day)
    bridge = _pick(_BRIDGES, variant, 10)
    closing = _pick(_CLOSINGS, variant, 15)
    pattern = _pick(_MESSAGE_PATTERNS, variant, 20)

    return pattern.format(
        greeting=f"<b>{greeting}</b>",
        intro=intro,
        bridge=bridge,
        bridge_lc=_lower_first(bridge),
        teaser=teaser,
        closing=closing,
        closing_lc=_lower_first(closing),
    )


def build_open_app_markup(label: str = DAILY_OPEN_APP_LABEL) -> dict | None:
    """Inline-keyboard with a single `web_app` button that opens the Mini App.
    Returns None if the WebApp URL is not configured (so callers can pass
    the result straight to send_message without conditionals)."""
    url = (settings.TELEGRAM_WEBAPP_URL or "").strip()
    if not url:
        return None
    return {
        "inline_keyboard": [
            [{"text": label, "web_app": {"url": url}}]
        ]
    }
