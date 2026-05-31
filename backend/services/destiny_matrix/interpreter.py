"""LLM-backed personal narrative for a Destiny Matrix reading.

Generates an 8-section warm Russian portrait (~700-900 words) from the
computed matrix numbers. Cached forever per reading_id in
destiny_matrix_interpretations.

Used by the /destiny-matrix/interpretation endpoint — never raises on
LLM failure (caller gets either real text or a generic fallback).
"""

from __future__ import annotations

from typing import Any, cast

from core.logging import get_logger
from services.destiny_matrix.arcana_names import ARCANA_NAMES_RU

log = get_logger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

# Соответствует §8 MATRIX_DESTINY_SPEC.md — JSON-контракт ответа модели.
SECTION_KEYS = (
    "who_you_are",
    "karmic_tail",
    "talents",
    "purpose",
    "relationships",
    "finance",
    "parental",
    "advice",
)

SECTION_LABELS_RU = {
    "who_you_are": "Кто вы",
    "karmic_tail": "Кармический хвост",
    "talents": "Таланты",
    "purpose": "Предназначение",
    "relationships": "Отношения",
    "finance": "Деньги и реализация",
    "parental": "Род и семья",
    "advice": "Совет",
}


_SYSTEM_PROMPT = """Ты — астролог-практик, эксперт по Матрице Судьбы (метод Ладини).
Пишешь тёплый, поддерживающий, конкретный персональный разбор.

Стиль:
- Обращайся на «ты», тепло, без формализма.
- Связный текст в каждой секции, не список значений арканов.
- Учитывай принцип «плюс/минус»: энергия не плохая, важно как проживается.
- Учитывай пол читателя, если он указан: арканы 3 (Императрица) и 4
  (Император), а также секции «Отношения» и «Род и семья» имеют разное
  звучание для мужчины и женщины. Не объясняй сам факт пола читателя —
  просто пиши на соответствующем тоне.
- Без мед/юр/инвест-советов и без предсказаний дат.
- Не используй фразы «звёзды говорят», «судьба предначертала» —
  ты наставник, а не предсказатель.

Длина: ~100 слов на каждую из 8 секций (всего 700-900 слов).
Возвращай результат ТОЛЬКО через вызов инструмента publish_reading."""


# Anthropic tool-use schema — modelo возвращает structured output, мы
# его декодируем безопасно из tool_use.input (никаких ручных JSON.parse).
_PUBLISH_TOOL = {
    "name": "publish_reading",
    "description": "Публикует персональный разбор Матрицы Судьбы в 8 секциях.",
    "input_schema": {
        "type": "object",
        "properties": {
            "who_you_are":   {"type": "string", "description": "Кто ты — характер, портрет личности."},
            "karmic_tail":   {"type": "string", "description": "Главный кармический урок этой жизни."},
            "talents":       {"type": "string", "description": "Зона талантов — что вдохновляет."},
            "purpose":       {"type": "string", "description": "Предназначение по возрастным этапам и миссии."},
            "relationships": {"type": "string", "description": "Какого партнёра притягиваешь и как строить отношения."},
            "finance":       {"type": "string", "description": "Канал денег: откуда приходят, профессии."},
            "parental":      {"type": "string", "description": "Детско-родительский канал и родовые программы."},
            "advice":        {"type": "string", "description": "Один практический совет на текущий период."},
        },
        "required": list(SECTION_KEYS),
    },
}


def _name(num: int) -> str:
    return ARCANA_NAMES_RU.get(num, f"Аркан {num}")


def _channel_line(label: str, ch: list[int]) -> str:
    """Format a 3-energy channel line: 'label: 13 → 21 → 7'."""
    nums = " → ".join(str(n) for n in ch)
    return f"- {label}: {nums}"


def _build_user_prompt(
    positions: dict[str, Any],
    first_name: str | None,
    gender: str | None = None,
) -> str:
    """Compose the user-facing payload — the numbers + arcana names that
    feed into the LLM. Numbers cited explicitly so the model anchors its
    interpretation to the actual computed matrix rather than free-styling."""

    name_line = f"Имя: {first_name}\n" if first_name else ""
    gender_line = ""
    if gender in ("male", "female"):
        gender_line = (
            f"Пол: {'мужчина' if gender == 'male' else 'женщина'}\n"
        )

    pers = positions["personality"]
    sq = positions["ancestral_square"]
    lines = positions["lines"]
    purp = positions["purposes"]
    ch = positions["channels"]
    varna = positions["varna"]

    parts = [
        "ЛИЧНОСТНЫЙ КВАДРАТ:",
        f"- День (портрет личности): {pers['day']} — {_name(pers['day'])}",
        f"- Месяц (таланты, что вдохновляет): {pers['month']} — {_name(pers['month'])}",
        f"- Год (опыт рода, повторы): {pers['year']} — {_name(pers['year'])}",
        f"- Низ (главный кармический урок): {pers['bottom']} — {_name(pers['bottom'])}",
        f"- Центр (характер, зона комфорта): {pers['center']} — {_name(pers['center'])}",
        "",
        "РОДОВОЙ КВАДРАТ:",
        f"- Верх слева (отец, духовное): {sq['top_left']} — {_name(sq['top_left'])}",
        f"- Верх справа (мать, духовное): {sq['top_right']} — {_name(sq['top_right'])}",
        f"- Низ справа (мать, материальное): {sq['bottom_right']} — {_name(sq['bottom_right'])}",
        f"- Низ слева (отец, материальное): {sq['bottom_left']} — {_name(sq['bottom_left'])}",
        "",
        "ЛИНИИ:",
        f"- Небо (вертикаль, духовное): {lines['sky']} — {_name(lines['sky'])}",
        f"- Земля (горизонталь, материя): {lines['earth']} — {_name(lines['earth'])}",
        f"- Линия отца: {lines['father']} — {_name(lines['father'])}",
        f"- Линия матери: {lines['mother']} — {_name(lines['mother'])}",
        "",
        "ПРЕДНАЗНАЧЕНИЯ:",
        f"- Личное (до ~40): {purp['personal']} — {_name(purp['personal'])}",
        f"- Социальное (40-60): {purp['social']} — {_name(purp['social'])}",
        f"- Духовное (после 60): {purp['spiritual']} — {_name(purp['spiritual'])}",
        f"- Планетарное (миссия): {purp['planetary']} — {_name(purp['planetary'])}",
        "",
        "КАНАЛЫ (3 энергии: вход → работа → итог):",
        _channel_line("Кармический хвост", ch["karmic_tail"]),
        _channel_line("Таланты", ch["talents"]),
        _channel_line("Отношения", ch["relationships"]),
        _channel_line("Финансы", ch["finance"]),
        _channel_line("Материальная карма", ch["material_karma"]),
        _channel_line("Детско-родительский", ch["parental"]),
        _channel_line("Род отца (таланты)", ch["ancestral_father_talents"]),
        _channel_line("Род отца (карма)", ch["ancestral_father_karma"]),
        _channel_line("Род матери (таланты)", ch["ancestral_mother_talents"]),
        _channel_line("Род матери (карма)", ch["ancestral_mother_karma"]),
        "",
        f"ВАРНА: {varna['varnas']} (экспрессия {varna['expression']})",
    ]

    return (
        f"{name_line}{gender_line}Матрица Судьбы — ключевые позиции:\n\n"
        + "\n".join(parts)
        + "\n\nНапиши персональный разбор по 8 секциям согласно системному промпту."
    )


def _fallback_sections(positions: dict[str, Any]) -> dict[str, str]:
    """Static fallback if LLM is unavailable. Generic, but matches the
    actual matrix numbers so user still sees their personal data."""
    pers = positions["personality"]
    purp = positions["purposes"]
    center_name = _name(pers["center"])
    bottom_name = _name(pers["bottom"])
    purpose_name = _name(purp["personal"])
    return {
        "who_you_are": (
            f"Твой характер тяготеет к энергии {center_name} — это твоя зона "
            "комфорта и привычный способ проявляться. Полное описание появится "
            "после обновления контента."
        ),
        "karmic_tail": (
            f"Главный кармический урок этой жизни — энергия {bottom_name}. "
            "Это то, что важно проработать, чтобы матрица раскрылась."
        ),
        "talents": "Описание зоны талантов готовится.",
        "purpose": (
            f"Личное предназначение до ~40 лет связано с энергией {purpose_name}. "
            "Это вектор, по которому растёт твоя личность."
        ),
        "relationships": "Описание канала отношений готовится.",
        "finance": "Описание финансового канала готовится.",
        "parental": "Описание родовых программ готовится.",
        "advice": "Доверяй своему центру и не торопи главные перемены.",
    }


async def generate_interpretation(
    positions: dict[str, Any],
    first_name: str | None,
    api_key: str | None,
    gender: str | None = None,
) -> tuple[dict[str, str], str]:
    """Returns (sections_dict, model_name_used). Falls back to static text
    if api_key is missing or LLM call fails — never raises.

    Uses Anthropic tool_use so structured output is parsed by the SDK —
    no fragile manual JSON parsing of free-form text (the old approach
    blew up on long replies because LLM rarely escapes embedded quotes
    or newlines correctly in 4 KB of prose).

    ``gender`` ('male' / 'female' / None) is forwarded into the prompt so
    arcana 3/4 and the relationships/family-and-kin sections get a tone
    appropriate to the reader. Missing/unknown gender renders a neutral
    reading (no «он/она» commitments)."""
    if not api_key:
        log.warning("destiny_matrix.interp.no_api_key")
        return _fallback_sections(positions), "fallback"

    import anthropic
    from anthropic.types import MessageParam, ToolChoiceToolParam, ToolParam

    user_prompt = _build_user_prompt(positions, first_name, gender)
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        tools = cast(list[ToolParam], [_PUBLISH_TOOL])
        tool_choice: ToolChoiceToolParam = {"type": "tool", "name": "publish_reading"}
        messages: list[MessageParam] = [{"role": "user", "content": user_prompt}]
        message = await client.messages.create(
            model=_MODEL,
            max_tokens=3000,
            system=_SYSTEM_PROMPT,
            tools=tools,
            tool_choice=tool_choice,
            messages=messages,
        )
        # Find the tool_use block — model is forced to it via tool_choice.
        tool_input: dict[str, Any] | None = None
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == "publish_reading":
                tool_input = getattr(block, "input", None)
                break
        if not isinstance(tool_input, dict):
            log.error("destiny_matrix.interp.no_tool_use",
                      stop_reason=getattr(message, "stop_reason", None))
            return _fallback_sections(positions), "fallback"

        sections: dict[str, str] = {}
        for key in SECTION_KEYS:
            text = str(tool_input.get(key, "")).strip()
            sections[key] = text if text else "Описание скоро появится."
        return sections, _MODEL
    except Exception as e:  # noqa: BLE001
        log.error("destiny_matrix.interp.failed", error=str(e)[:300])
        return _fallback_sections(positions), "fallback"
