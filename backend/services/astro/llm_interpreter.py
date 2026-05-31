"""
LLM-based natal chart interpretation via Anthropic Claude.

Generates a holistic, personal reading in Russian from raw chart data.
Result is cached by the caller — this function always calls the API.
"""

from __future__ import annotations

from core.logging import get_logger
from services.llm_utils import first_text_block

log = get_logger(__name__)

from services.astro.planet_names import PLANET_RU as _PLANET_RU  # noqa: E402

_ASPECT_RU: dict[str, str] = {
    "conjunction": "соединение", "trine": "трин",
    "square": "квадрат", "opposition": "оппозиция", "sextile": "секстиль",
}


def _build_prompt(
    sun_sign: str,
    moon_sign: str,
    ascendant_sign: str | None,
    planets: dict,
    aspects: list,
) -> str:
    planet_lines: list[str] = []
    for key, ru_name in _PLANET_RU.items():
        if key in planets:
            p = planets[key]
            retro = " (ретроградный)" if p.get("retrograde") else ""
            planet_lines.append(
                f"- {ru_name}: {p.get('sign_ru') or p.get('sign', '?')} "
                f"{p.get('sign_degree', 0):.0f}°, {p.get('house', '?')}-й дом{retro}"
            )

    sorted_aspects = sorted(aspects, key=lambda a: a.get("orb", 99))[:6]
    aspect_lines: list[str] = []
    for a in sorted_aspects:
        p1 = _PLANET_RU.get(a.get("p1", "").lower(), a.get("p1", ""))
        p2 = _PLANET_RU.get(a.get("p2", "").lower(), a.get("p2", ""))
        asp = _ASPECT_RU.get(a.get("aspect", ""), a.get("aspect", ""))
        orb = a.get("orb", 0)
        aspect_lines.append(f"- {p1} — {asp} — {p2} (орб {orb:.1f}°)")

    asc_line = f"Асцендент: {ascendant_sign}" if ascendant_sign else ""

    return f"""Ты пишешь персональный разбор натальной карты для популярного приложения с астрологией. Читатель — обычный человек, не астролог. Многие открывают свою карту впервые.

Данные карты:
Солнце: {sun_sign}
Луна: {moon_sign}
{asc_line}

Планеты:
{chr(10).join(planet_lines)}

Ключевые аспекты:
{chr(10).join(aspect_lines) if aspect_lines else '— нет данных'}

Напиши развёрнутый личный разбор (1000–1400 слов) в семи разделах. Каждый раздел начни с названия, обёрнутого в **двойные звёздочки**, на отдельной строке, потом обычный текст полноценными абзацами. Парсер на фронте разбивает текст по `**Название**`, без звёздочек всё схлопнется в один блок.

Используй ровно эти семь заголовков:

**Ядро личности**
2–3 абзаца о Солнце, Луне и Асценденте — какой вы внутри, как чувствуете, как выглядите для других и где между этими слоями бывает напряжение.

**Ум и общение**
1–2 абзаца о Меркурии — как думаете, учитесь, разговариваете, спорите, принимаете решения и объясняете свои идеи.

**Любовь и ценности**
1–2 абзаца о Венере — что вам нравится, как влюбляетесь, что считаете красивым, как выбираете близость и что для вас является настоящей ценностью.

**Энергия и воля**
1–2 абзаца о Марсе — как действуете, спорите, защищаете границы, идёте к своему и что помогает не выгорать.

**Удача и вызовы**
2 абзаца о Юпитере и Сатурне: где везёт и легко расширяться, а где приходится трудиться, взрослеть и строить устойчивую опору.

**Ключевые аспекты**
2–3 абзаца о двух-трёх важнейших аспектах из списка — как они проявляются в характере, отношениях, работе, привычных реакциях и повторяющихся сценариях.

**Совет и путь**
1–2 абзаца с практическим советом — куда расти, на что обратить внимание, какие сильные стороны использовать и какие привычки мягко перенастроить.

КАК ПИСАТЬ:
- Живой человеческий язык, как будто рассказываешь хорошему знакомому про него самого.
- Конкретные жизненные образы: работа, отношения, разговоры, привычки, реакции.
- Без астрологического жаргона: ни «энергии», ни «архетипы», ни «вселенная учит», ни «эманации».
- Без банальностей вроде «вы — сильная и независимая личность».
- Обращайся на «вы», но без официоза.
- Кроме `**Заголовка**` никакого markdown — ни решёток, ни списков, ни звёздочек внутри текста."""


async def generate_natal_reading(
    sun_sign: str,
    moon_sign: str,
    ascendant_sign: str | None,
    planets: dict,
    aspects: list,
    api_key: str,
) -> str:
    """
    Call Claude to generate a natal chart reading in Russian.
    Raises on API error — caller should catch and handle gracefully.
    """
    import anthropic

    prompt = _build_prompt(sun_sign, moon_sign, ascendant_sign, planets, aspects)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2400,
        messages=[{"role": "user", "content": prompt}],
    )

    text = first_text_block(message.content)
    log.info("llm_interpreter.done", chars=len(text))
    return text
