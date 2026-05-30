"""LLM-backed text interpretations for current transits.

Mirrors services/astro/synastry_interpreter but with a transit-framed
prompt ("right now planet X is making this aspect to your natal Y").
Cache lives in transit_interpretations (planet order matters here).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from db.database import AsyncSessionLocal
from db.models import TransitInterpretation
from services.llm_utils import first_text_block

log = get_logger(__name__)

from services.astro.planet_names import PLANET_RU as _PLANET_RU  # noqa: E402

_ASPECT_RU: dict[str, str] = {
    "conjunction": "соединение", "trine": "трин",
    "square": "квадрат", "opposition": "оппозиция", "sextile": "секстиль",
}

# Last-resort copy when we have no LLM key and no cache row. Generic but
# casual — better than nothing while we wait for LLM to fill the gap.
_FALLBACK: dict[str, str] = {
    "conjunction": "Две темы сливаются в одну сильную волну — то, что раньше"
    " казалось разным, сегодня работает вместе.",
    "trine": "Сегодня всё складывается само — стоит сделать шаг, и поддержка"
    " найдётся.",
    "sextile": "Окно возможностей открыто, но само не зайдёт — нужен ваш ход.",
    "square": "Что-то трётся и мешает. Это не катастрофа — это место, где"
    " вы реально вырастете.",
    "opposition": "Внутри тянет в две стороны сразу. Не выбирайте крайность —"
    " попробуйте найти баланс.",
}


async def _llm_batch(
    missing: list[tuple[str, str, str]],
    api_key: str,
) -> dict[tuple[str, str, str], str]:
    """One LLM call producing N interpretations (transit-framed)."""
    if not missing:
        return {}

    import anthropic

    items = []
    for i, (tp, np, aspect) in enumerate(missing):
        items.append(
            f"{i + 1}. Транзитный {_PLANET_RU.get(tp, tp)} — "
            f"{_ASPECT_RU.get(aspect, aspect)} — натальный {_PLANET_RU.get(np, np)}"
        )

    prompt = f"""Ты пишешь короткие посты для популярного приложения с астрологией. Аудитория — обычные люди, не астрологи. Многие из них в первый раз сталкиваются с темой транзитов.

Транзиты:
{chr(10).join(items)}

Для каждого транзита напиши пост в 3-4 предложения (60-100 слов).

КАК ПИСАТЬ:
- Живой разговорный язык, как будто рассказываешь другу за кофе.
- Конкретные образы из обычной жизни: работа, отношения, деньги, разговоры, домашние дела.
- Один-два прямых совета: что попробовать сегодня, на что обратить внимание, чего лучше избежать.
- Обращайся на «вы», но без официоза.

ЧЕГО НЕ ДЕЛАТЬ:
- Никакого астрологического жаргона: ни «энергии», ни «вселенная подарит», ни «планеты учат», ни «эманации», ни «архетипы».
- Никаких заголовков, звёздочек, markdown, эмодзи.
- Не начинай с «Транзит...» или «Сегодня...». Начинай сразу с сути.
- Не повторяй название планет и аспекта в начале — пользователь и так его видит сверху.

ЧТО УЧИТЫВАТЬ:
- О чём «работает» транзитная планета: Венера — отношения, удовольствие, деньги, эстетика; Марс — действия, спор, спорт, желания; Меркурий — мысли, разговоры, переписки, мелкие дела; Луна — настроение и быт; Солнце — самоощущение, признание; Юпитер — рост, возможности, оптимизм; Сатурн — ответственность, границы, дисциплина; Уран — внезапное и свободное; Нептун — мечты, иллюзии, творчество; Плутон — глубокие изменения; Хирон — старые раны и их исцеление.
- Оси и точки карты: Асцендент — то, как вы выглядите для других и первое впечатление; Десцендент — близкие отношения и партнёры; Середина неба — карьера, публичный образ; Глубина неба — дом, семья, корни; Северный узел — направление роста; Южный узел — то, что пора отпустить; Лилит — теневая, неудобная сторона себя.
- Какая натальная тема активируется (та же логика для натальной планеты).
- Характер аспекта: трин/секстиль — поток и поддержка; квадрат/оппозиция — напряжение, выбор, трение; соединение — две темы сливаются в одну.

Верни ТОЛЬКО JSON-массив строк в порядке списка, без обёртки. Пример: ["текст1", "текст2", ...]"""

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = first_text_block(message.content).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()
        texts = json.loads(raw)
        if not isinstance(texts, list) or len(texts) != len(missing):
            log.warning(
                "transit_interp.llm_shape_mismatch",
                expected=len(missing),
                got=len(texts) if isinstance(texts, list) else "non-list",
            )
            return {}
        return {triple: str(text).strip() for triple, text in zip(missing, texts) if text}
    except Exception as e:  # noqa: BLE001
        log.error("transit_interp.llm_failed", error=str(e), count=len(missing))
        return {}


def _extract_triples(
    aspects: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    triples: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for a in aspects:
        tp = (a.get("transit_planet") or "").lower()
        np = (a.get("natal_planet") or "").lower()
        ap = (a.get("aspect") or "").lower()
        if not tp or not np or not ap:
            continue
        triple = (tp, np, ap)
        if triple in seen:
            continue
        seen.add(triple)
        triples.append(triple)
    return triples


async def _lookup_cached(
    db: AsyncSession,
    triples: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], str]:
    if not triples:
        return {}
    cached: dict[tuple[str, str, str], str] = {}
    result = await db.execute(
        select(
            TransitInterpretation.transit_planet,
            TransitInterpretation.natal_planet,
            TransitInterpretation.aspect,
            TransitInterpretation.text_ru,
        ).where(
            tuple_(
                TransitInterpretation.transit_planet,
                TransitInterpretation.natal_planet,
                TransitInterpretation.aspect,
            ).in_(triples)
        )
    )
    for row in result:
        cached[(row.transit_planet, row.natal_planet, row.aspect)] = row.text_ru
    return cached


async def _background_generate(
    missing: list[tuple[str, str, str]],
    api_key: str,
    on_complete: Callable[[], Awaitable[None]] | None,
) -> None:
    """Fire-and-forget: generate LLM texts in a fresh DB session, then
    optionally invoke `on_complete` so the route layer can invalidate the
    Redis cache key it just populated with fallback text."""
    try:
        generated = await _llm_batch(missing, api_key)
        if generated:
            async with AsyncSessionLocal() as bg_db:
                for triple, text in generated.items():
                    bg_db.add(
                        TransitInterpretation(
                            transit_planet=triple[0],
                            natal_planet=triple[1],
                            aspect=triple[2],
                            text_ru=text,
                        )
                    )
                try:
                    await bg_db.commit()
                except Exception as e:  # noqa: BLE001
                    log.warning("transit_bg.cache_collision", error=str(e))
        if on_complete:
            try:
                await on_complete()
            except Exception as e:  # noqa: BLE001
                log.warning("transit_bg.on_complete_failed", error=str(e))
    except Exception as e:  # noqa: BLE001
        log.error("transit_bg.failed", error=str(e), count=len(missing))


async def get_or_generate_transit_texts(
    db: AsyncSession,
    aspects: list[dict[str, Any]],
    api_key: str | None,
    *,
    blocking: bool = True,
    on_background_complete: Callable[[], Awaitable[None]] | None = None,
) -> tuple[dict[tuple[str, str, str], str], int]:
    """For each transit, return (texts_by_triple, missing_count).

    With `blocking=True` (default), waits for the LLM call to populate any
    missing entries before returning — used internally for non-user-facing
    flows. With `blocking=False`, returns immediately with cache + fallback
    and schedules an asyncio background task to fill the gap. The optional
    `on_background_complete` lets the caller invalidate its Redis cache so
    the next request gets the freshly generated text.
    """
    if not aspects:
        return {}, 0

    triples = _extract_triples(aspects)
    if not triples:
        return {}, 0

    cached = await _lookup_cached(db, triples)
    missing = [t for t in triples if t not in cached]

    if missing and api_key:
        if blocking:
            generated = await _llm_batch(missing, api_key)
            for triple, text in generated.items():
                db.add(
                    TransitInterpretation(
                        transit_planet=triple[0],
                        natal_planet=triple[1],
                        aspect=triple[2],
                        text_ru=text,
                    )
                )
                cached[triple] = text
            if generated:
                try:
                    await db.flush()
                except Exception as e:  # noqa: BLE001
                    log.warning("transit_interp.cache_collision", error=str(e))
            missing = [t for t in triples if t not in cached]
        else:
            # Hand the LLM call to a background task. Use a copy so we
            # don't capture a mutable reference.
            asyncio.create_task(
                _background_generate(list(missing), api_key, on_background_complete)
            )

    for triple in triples:
        cached.setdefault(triple, _FALLBACK.get(triple[2], ""))

    return cached, len(missing)


# ── Deep-dive ("What does this mean for me") ─────────────────────────────────

# House → life-sphere topic. Mass-market friendly framing.
_HOUSE_TOPIC: dict[int, str] = {
    1: "Самоощущение и образ",
    2: "Деньги и ресурсы",
    3: "Общение и ближний круг",
    4: "Дом и семья",
    5: "Творчество и удовольствия",
    6: "Работа и здоровье",
    7: "Близкие отношения",
    8: "Глубокие изменения и общие ресурсы",
    9: "Рост, учёба, дальние горизонты",
    10: "Карьера и публичный образ",
    11: "Друзья и большие цели",
    12: "Внутренний мир и уединение",
}


async def _llm_advice(
    tp: str,
    np: str,
    aspect: str,
    text_blurb: str,
    api_key: str,
) -> tuple[str | None, str | None]:
    """Generate (advice_do, advice_avoid) for a single transit triple.
    One LLM call → two short bulletized lists.
    """
    import anthropic

    tp_ru = _PLANET_RU.get(tp, tp)
    np_ru = _PLANET_RU.get(np, np)
    aspect_ru = _ASPECT_RU.get(aspect, aspect)

    prompt = f"""Транзит: {tp_ru} ({aspect_ru}) к натальной точке {np_ru}.
Уже написанный короткий разбор этого транзита:
"{text_blurb}"

Теперь напиши практическое руководство на сегодня. Два блока:

1) ЧТО СДЕЛАТЬ — 2-3 коротких конкретных совета. Каждый совет — одна фраза, начинается с глагола. Без эзотерики, без «вселенная», «энергии», «работа со страхами». Только конкретные действия из обычной жизни.

2) ЧЕГО ИЗБЕГАТЬ — 2-3 коротких предупреждения. Тоже конкретно, тоже одной фразой каждое.

Тон: разговорный, как друг советует. Обращайся на «вы». Без markdown, без нумерации внутри блоков — разделяй советы переносом строки.

Верни ТОЛЬКО JSON следующего вида:
{{"do": "Совет 1\\nСовет 2\\nСовет 3", "avoid": "Предупреждение 1\\nПредупреждение 2"}}"""

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = first_text_block(message.content).strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()
        data = json.loads(raw)
        do_ = str(data.get("do", "")).strip() or None
        avoid_ = str(data.get("avoid", "")).strip() or None
        return do_, avoid_
    except Exception as e:  # noqa: BLE001
        log.error("transit_advice.llm_failed", tp=tp, np=np, aspect=aspect, error=str(e))
        return None, None


async def get_transit_details(
    db: AsyncSession,
    transit_planet: str,
    natal_planet: str,
    aspect: str,
    natal_chart: dict[str, Any] | None,
    api_key: str | None,
) -> dict[str, Any]:
    """Look up (or generate) the deep-dive payload for a single transit.

    Returns dict with `text_ru`, `advice_do`, `advice_avoid`,
    `affected_house` (int | None) and `affected_house_topic` (str | None).
    """
    tp = transit_planet.lower()
    np = natal_planet.lower()
    ap = aspect.lower()

    result = await db.execute(
        select(TransitInterpretation).where(
            TransitInterpretation.transit_planet == tp,
            TransitInterpretation.natal_planet == np,
            TransitInterpretation.aspect == ap,
        )
    )
    row = result.scalar_one_or_none()
    text_ru = row.text_ru if row else _FALLBACK.get(ap, "")
    advice_do = row.advice_do if row else None
    advice_avoid = row.advice_avoid if row else None

    if (advice_do is None or advice_avoid is None) and api_key:
        do_, avoid_ = await _llm_advice(tp, np, ap, text_ru or "", api_key)
        if do_ or avoid_:
            advice_do = advice_do or do_
            advice_avoid = advice_avoid or avoid_
            if row:
                await db.execute(
                    update(TransitInterpretation)
                    .where(TransitInterpretation.id == row.id)
                    .values(advice_do=advice_do, advice_avoid=advice_avoid)
                )
            else:
                db.add(
                    TransitInterpretation(
                        transit_planet=tp,
                        natal_planet=np,
                        aspect=ap,
                        text_ru=text_ru or _FALLBACK.get(ap, ""),
                        advice_do=advice_do,
                        advice_avoid=advice_avoid,
                    )
                )
            try:
                await db.flush()
            except Exception as e:  # noqa: BLE001
                log.warning("transit_advice.cache_collision", error=str(e))

    affected_house: int | None = None
    affected_house_topic: str | None = None
    if natal_chart and isinstance(natal_chart, dict):
        planets = natal_chart.get("planets") or {}
        planet_data = planets.get(np) or planets.get(natal_planet)
        if isinstance(planet_data, dict):
            raw_house = planet_data.get("house")
            if isinstance(raw_house, (int, float)):
                affected_house = int(raw_house)
                affected_house_topic = _HOUSE_TOPIC.get(affected_house)

    return {
        "text_ru": text_ru,
        "advice_do": advice_do,
        "advice_avoid": advice_avoid,
        "affected_house": affected_house,
        "affected_house_topic": affected_house_topic,
    }
