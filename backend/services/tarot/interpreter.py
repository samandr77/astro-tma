"""
LLM-based tarot narrative interpretation via Anthropic Claude.

Supports all 4 spread types: three_card, celtic_cross, week, relationship.
Each subsequent card is explained in the context of previous cards to build
one coherent story, plus a final summary with practical suggestions.

Result is structured data (positions + summary), cached by reading_id.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import get_logger
from services.llm_utils import first_text_block

log = get_logger(__name__)


# ── Per-spread metadata ───────────────────────────────────────────────────────

_SPREADS: dict[str, dict[str, Any]] = {
    "three_card": {
        "title": "Прошлое · Настоящее · Будущее",
        "intro": (
            "Классический трёхкарточный расклад: корни ситуации, "
            "текущее состояние и направление движения."
        ),
        "positions": {
            1: "Прошлое — события и энергии, приведшие к текущей ситуации",
            2: "Настоящее — актуальное состояние, ключевые силы момента",
            3: "Будущее — вероятное развитие при сохранении траектории",
        },
    },
    "celtic_cross": {
        "title": "Кельтский крест",
        "intro": (
            "Глубокий 10-карточный расклад. Позиции 1–6 — Крест, "
            "исследует текущую реальность. Позиции 7–10 — Посох, "
            "раскрывает путь к разрешению."
        ),
        "positions": {
            1: "Суть — текущее состояние, центральный вопрос",
            2: "Препятствие — то, что мешает или противодействует",
            3: "Сознание — осознанная цель, мысли и видимый ориентир",
            4: "Подсознание — фундамент ситуации и скрытые причины",
            5: "Прошлое — уходящие события, ещё влияющие на настоящее",
            6: "Будущее — ближайшая фаза развития",
            7: "Я сам — ваше отношение и самовосприятие",
            8: "Другие — внешние влияния, люди и обстоятельства",
            9: "Надежды и опасения — то, чего желаете или боитесь",
            10: "Исход — вероятное разрешение, если энергии сохранятся",
        },
    },
    "week": {
        "title": "Карта на каждый день",
        "intro": (
            "Энергетический рисунок ближайших семи дней: где лёгкость, "
            "где сопротивление, на что направить внимание."
        ),
        "positions": {
            1: "Луна — эмоциональный тон ближайшего периода",
            2: "Марс — где потребуется действие и смелость",
            3: "Меркурий — мысли, разговоры и важные решения",
            4: "Юпитер — рост, поддержка и возможности",
            5: "Венера — отношения, удовольствие и ценности",
            6: "Сатурн — ответственность, границы и урок недели",
            7: "Солнце — итоговая ясность и главный фокус",
        },
    },
    "relationship": {
        "title": "Расклад на отношения",
        "intro": (
            "Пять карт показывают позиции обоих партнёров, качество связи, "
            "главный вызов и потенциал развития отношений."
        ),
        "positions": {
            1: "Вы — ваша роль и состояние в отношениях",
            2: "Партнёр — позиция и состояние другого человека",
            3: "Связь — качество и природа того, что между вами",
            4: "Вызов — главное препятствие или напряжение",
            5: "Потенциал — куда могут развиться отношения",
        },
    },
}


# ── Prompt construction ───────────────────────────────────────────────────────

def _build_prompt(spread_type: str, cards: list[dict[str, Any]]) -> str:
    meta = _SPREADS[spread_type]
    positions_meta: dict[int, str] = meta["positions"]
    expected_n = len(positions_meta)

    lines: list[str] = []
    for i, c in enumerate(cards, start=1):
        orient = "перевёрнута" if c.get("reversed") else "прямая"
        lines.append(
            f"Позиция {i} ({positions_meta[i]}):\n"
            f"  Карта: {c['name_ru']} ({orient})\n"
            f"  Ключевые слова: {', '.join(c.get('keywords_ru') or [])}"
        )
    cards_block = "\n\n".join(lines)

    context_clause = (
        "Для позиции 1 опиши просто её значение в контексте позиции. "
        "Начиная с позиции 2, в каждой интерпретации ЯВНО связывай карту "
        "с тем, что уже было открыто (минимум одна отсылка к карте из предыдущих позиций)."
    ) if expected_n > 1 else (
        "Это одна карта — раскрой её значение в контексте позиции."
    )

    json_positions = ",\n    ".join(
        f'{{"n": {i}, "narrative": "<2–3 предложения>"}}'
        for i in range(1, expected_n + 1)
    )

    return f"""Ты делаешь расклад «{meta["title"]}» для популярного приложения. Читатели — обычные люди, не тарологи и не эзотерики.

{meta["intro"]}

Расклад ({expected_n} карт):

{cards_block}

Составь интерпретацию в виде ОДНОЙ цельной истории. {context_clause}

Верни СТРОГО валидный JSON без markdown-обёрток, следующей формы:
{{
  "positions": [
    {json_positions}
  ],
  "summary": "<80–120 слов: общий вывод и один конкретный совет на основе всего расклада>"
}}

КАК ПИСАТЬ:
- Живой человеческий язык, как будто рассказываешь близкой подруге.
- Конкретные образы из жизни: работа, отношения, разговоры, выбор, привычки.
- Без эзотерического жаргона: ни «вселенная говорит», ни «энергии карт», ни «архетипы», ни «эманации».
- Без банальностей в духе «карты говорят, что вы на верном пути».
- В позициях не пересказывай описание карты — раскрывай её смысл именно в этой роли и в связи с предыдущими картами.
- Summary должен синтезировать историю и закончиться 1-2 практичными советами.
- Обращайся на «вы», но по-человечески, без официоза."""


def _extract_json(text: str) -> dict[str, Any]:
    """Strip potential code fences and return parsed JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("{"):
        l = cleaned.find("{")
        r = cleaned.rfind("}")
        if l >= 0 and r > l:
            cleaned = cleaned[l : r + 1]
    return json.loads(cleaned)


# ── Public entry point ────────────────────────────────────────────────────────

def is_supported_spread(spread_type: str) -> bool:
    return spread_type in _SPREADS


def expected_card_count(spread_type: str) -> int:
    return len(_SPREADS[spread_type]["positions"])


async def generate_spread_interpretation(
    spread_type: str,
    cards: list[dict[str, Any]],
    api_key: str,
) -> dict[str, Any]:
    """
    Call Claude to generate a narrative interpretation for the given spread.

    `cards` must have exactly `expected_card_count(spread_type)` items, each
    a dict with at least: name_ru, reversed, keywords_ru.
    Returns dict: {"positions": [...N...], "summary": str}.
    Raises on API / JSON / count mismatch — caller should handle.
    """
    import anthropic

    if not is_supported_spread(spread_type):
        raise ValueError(f"unsupported spread: {spread_type!r}")

    expected_n = expected_card_count(spread_type)
    if len(cards) != expected_n:
        raise ValueError(
            f"expected {expected_n} cards for {spread_type}, got {len(cards)}"
        )

    prompt = _build_prompt(spread_type, cards)

    # max_tokens scaled to spread size: ~70 tokens per position (3 sentences)
    # + 200 tokens summary + a safety margin. Caps growth on big spreads
    # (celtic 10 cards) without truncating the smaller ones.
    cap = 600 + expected_n * 180

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=cap,
        messages=[{"role": "user", "content": prompt}],
    )

    text = first_text_block(message.content)
    parsed = _extract_json(text)

    positions_raw = parsed.get("positions", [])
    by_n = {int(p["n"]): str(p.get("narrative", "")).strip() for p in positions_raw}
    positions = [
        {"n": n, "narrative": by_n.get(n, "")}
        for n in range(1, expected_n + 1)
    ]
    summary = str(parsed.get("summary", "")).strip()

    log.info(
        "tarot.interpret.done",
        spread=spread_type,
        chars_summary=len(summary),
        pos_filled=sum(1 for p in positions if p["narrative"]),
    )
    return {"positions": positions, "summary": summary}


# Backwards compatibility — existing import path in routes/tarot.py
async def generate_celtic_cross_interpretation(
    cards: list[dict[str, Any]],
    api_key: str,
) -> dict[str, Any]:
    return await generate_spread_interpretation("celtic_cross", cards, api_key)
