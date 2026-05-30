"""
LLM-based daily horoscope generation via Anthropic Claude Haiku.

Generates unique daily horoscope texts in Russian for all 12 zodiac signs.
Called by APScheduler at 00:05 UTC nightly.
"""

from datetime import date

from core.logging import get_logger
from core.settings import settings
from services.llm_utils import first_text_block

log = get_logger(__name__)

_SIGN_RU: dict[str, str] = {
    "aries": "Овен", "taurus": "Телец", "gemini": "Близнецы",
    "cancer": "Рак", "leo": "Лев", "virgo": "Дева",
    "libra": "Весы", "scorpio": "Скорпион", "sagittarius": "Стрелец",
    "capricorn": "Козерог", "aquarius": "Водолей", "pisces": "Рыбы",
}

_SIGN_RULERS: dict[str, str] = {
    "aries": "Марс", "taurus": "Венера", "gemini": "Меркурий",
    "cancer": "Луна", "leo": "Солнце", "virgo": "Меркурий",
    "libra": "Венера", "scorpio": "Плутон", "sagittarius": "Юпитер",
    "capricorn": "Сатурн", "aquarius": "Уран", "pisces": "Нептун",
}

_SIGN_ELEMENTS: dict[str, str] = {
    "aries": "огонь", "taurus": "земля", "gemini": "воздух",
    "cancer": "вода", "leo": "огонь", "virgo": "земля",
    "libra": "воздух", "scorpio": "вода", "sagittarius": "огонь",
    "capricorn": "земля", "aquarius": "воздух", "pisces": "вода",
}


_WEEKDAY_RU = [
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
]


def _ru_weekday(d: date) -> str:
    """Russian weekday name only — no date or year. We pass weekday
    explicitly because Haiku is unreliable at computing it from a date."""
    return _WEEKDAY_RU[d.weekday()]


def _build_horoscope_prompt(sign: str, target_date: date, period: str = "today") -> str:
    sign_ru = _SIGN_RU.get(sign, sign)
    ruler = _SIGN_RULERS.get(sign, "")
    element = _SIGN_ELEMENTS.get(sign, "")

    weekday = _ru_weekday(target_date)
    period_desc = {
        "today": f"на сегодня ({weekday})",
        "tomorrow": f"на завтра ({weekday})",
        "week": "на эту неделю",
        "month": "на этот месяц",
    }.get(period, "на сегодня")

    return f"""Ты пишешь короткие гороскопы для популярного приложения. Читатели — обычные люди, не астрологи.

Гороскоп {period_desc} для знака {sign_ru} (стихия — {element}, управитель — {ruler}). Если упоминаешь день недели, используй именно: {weekday}.

ЧТО НУЖНО НАПИСАТЬ (4-6 предложений):
- Главный тон периода — что приходит, на что обратить внимание.
- Затронь 2-3 жизненные сферы: работа/деньги, отношения/общение, энергия/здоровье.
- Закончи одним конкретным советом — что попробовать или чего избежать.

КАК ПИСАТЬ:
- Живой человеческий язык, как будто рассказываешь подруге за кофе.
- Конкретные образы из жизни: переписки, встречи, рабочие задачи, домашние дела.
- Без астрологического жаргона: ни «энергии», ни «вселенная подарит», ни «эманации», ни «работа со страхами».
- Без банальностей в духе «звёзды благоволят» и «впереди новые возможности».
- Варьируй начало — не начинай с «Сегодня…».
- Обращайся на «вы», без официоза.
- Без emoji, без markdown, без заголовков.

Ответь ТОЛЬКО текстом гороскопа."""


async def generate_daily_horoscope(
    sign: str,
    target_date: date | None = None,
    period: str = "today",
) -> str | None:
    """Generate a single horoscope text via Claude Haiku. Returns None on failure."""
    if not settings.ANTHROPIC_API_KEY:
        log.warning("llm_horoscope.no_api_key")
        return None

    target_date = target_date or date.today()

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = _build_horoscope_prompt(sign, target_date, period)

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = first_text_block(message.content).strip()
        log.info("llm_horoscope.generated", sign=sign, period=period, chars=len(text))
        return text
    except Exception as e:
        log.error("llm_horoscope.failed", sign=sign, error=str(e))
        return None


async def generate_energy_scores_llm(sign: str, target_date: date) -> dict[str, int]:
    """Generate energy scores via LLM. Returns dict with love/career/health/luck (0-100)."""
    if not settings.ANTHROPIC_API_KEY:
        return _fallback_scores(sign)

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        sign_ru = _SIGN_RU.get(sign, sign)

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    f"Оцени энергии для {sign_ru} на {target_date.strftime('%d.%m.%Y')} "
                    f"по шкале 40-95. Ответь ТОЛЬКО в формате: "
                    f"love:XX career:XX health:XX luck:XX"
                ),
            }],
        )
        text = first_text_block(message.content).strip()
        scores = {}
        for pair in text.split():
            if ":" in pair:
                k, v = pair.split(":", 1)
                k = k.strip().lower()
                if k in ("love", "career", "health", "luck"):
                    scores[k] = max(20, min(95, int(v.strip())))
        if len(scores) == 4:
            return scores
    except Exception as e:
        log.error("llm_scores.failed", sign=sign, error=str(e))

    return _fallback_scores(sign)


def _fallback_scores(sign: str) -> dict[str, int]:
    """Deterministic fallback scores based on sign + date."""
    import hashlib
    h = hashlib.md5(f"{sign}{date.today().isoformat()}".encode()).hexdigest()
    base = [int(h[i:i+2], 16) for i in range(0, 8, 2)]
    return {
        "love": 40 + base[0] % 50,
        "career": 40 + base[1] % 50,
        "health": 45 + base[2] % 45,
        "luck": 35 + base[3] % 55,
    }
