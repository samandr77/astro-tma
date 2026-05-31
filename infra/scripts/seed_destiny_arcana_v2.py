#!/usr/bin/env python3
"""V2 seeder for `arcana_meanings` — 22 arcana × 9 contexts with
`meaning`, `plus`, `minus`, `professions` filled by Claude Haiku.

Each LLM call covers ONE arcana and returns all 9 contexts at once via
Anthropic `tool_use` (so we don't have to parse loose JSON). Writes
gender='any' rows. Gender overrides can be added in a follow-up pass
without re-running this script (the unique constraint is on
``(arcana_num, context, gender)``).

Cost: ~$3-5 in Haiku 4.5 tokens, ~3-5 minutes wall-clock.

Run:
    docker compose exec backend python /app/infra/scripts/seed_destiny_arcana_v2.py
    # idempotent, only fills missing rows:
    docker compose exec backend python /app/infra/scripts/seed_destiny_arcana_v2.py --missing-only
    # dry run prints to stdout:
    docker compose exec backend python /app/infra/scripts/seed_destiny_arcana_v2.py --dry-run

Notes:
    * Without --wipe, an existing row is updated in place (ON CONFLICT
      DO UPDATE on the V2 unique constraint).
    * `professions` is only populated for contexts where careers make
      sense — `finance` and `material_karma`. Other contexts get NULL.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, cast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from core.settings import settings  # noqa: E402
from db.database import AsyncSessionLocal  # noqa: E402
from db.models import ArcanaMeaning  # noqa: E402
from services.destiny_matrix.arcana_names import (  # noqa: E402
    ARCANA_KEYWORDS_RU,
    ARCANA_NAMES_RU,
    CONTEXTS,
)

_MODEL = "claude-haiku-4-5-20251001"

_CONTEXT_BRIEFS = {
    "personality": "ЛИЧНОСТЬ — характер, портрет, зона комфорта (центр/портрет ромба).",
    "talents":      "ТАЛАНТЫ — высшая суть, что вдохновляет, дар (месяц/верх ромба).",
    "purpose":      "ПРЕДНАЗНАЧЕНИЕ — миссия, вектор реализации (ЛП/СП/ДП/ПЛ).",
    "parental":     "ДЕТСКО-РОДИТЕЛЬСКИЙ — задача в роли ребёнка или родителя.",
    "ancestral":    "РОДОВАЯ ПРОГРАММА — что транслирует род (таланты сверху, карма снизу).",
    "relationships": "ОТНОШЕНИЯ — какого партнёра притягиваете, что мешает близости.",
    "finance":      "ФИНАНСЫ — откуда деньги, подходящие профессии, риски.",
    "material_karma": "МАТЕРИАЛЬНАЯ КАРМА — прошлый опыт, готовый ресурс.",
    "karmic_tail":  "КАРМИЧЕСКИЙ ХВОСТ — главный урок этой жизни.",
}

_CONTEXTS_WITH_PROFESSIONS = {"finance", "material_karma"}


def _tool_schema() -> dict[str, Any]:
    """Anthropic tool_use schema — one tool that returns all 9 contexts at once."""
    context_props: dict[str, Any] = {}
    for ctx in CONTEXTS:
        props = {
            "meaning": {
                "type": "string",
                "description": (
                    "Тёплый, конкретный, человеческий текст 60-90 слов о том, "
                    "как этот аркан работает в данном контексте. Без эзотерики, "
                    "без «вселенная даст», без жаргона. Обращение на «вы»."
                ),
            },
            "plus": {
                "type": "string",
                "description": (
                    "20-30 слов: что значит «в плюсе» — здоровое, ресурсное "
                    "проявление аркана в этом контексте. Одно-два предложения."
                ),
            },
            "minus": {
                "type": "string",
                "description": (
                    "20-30 слов: что значит «в минусе» — теневое, "
                    "нересурсное проявление. Одно-два предложения."
                ),
            },
        }
        if ctx in _CONTEXTS_WITH_PROFESSIONS:
            props["professions"] = {
                "type": "string",
                "description": (
                    "15-25 слов: список 4-6 профессий через запятую без вводных слов."
                ),
            }
        context_props[ctx] = {
            "type": "object",
            "properties": props,
            "required": ["meaning", "plus", "minus"] + (
                ["professions"] if ctx in _CONTEXTS_WITH_PROFESSIONS else []
            ),
        }

    return {
        "name": "publish_arcana_meanings",
        "description": (
            "Публикует тексты-расшифровки одного аркана в 9 жизненных "
            "контекстах. Гендерно-нейтрально (gender='any')."
        ),
        "input_schema": {
            "type": "object",
            "properties": context_props,
            "required": list(CONTEXTS),
        },
    }


def _build_prompt(arcana_num: int, name: str, keywords: list[str]) -> str:
    contexts_block = "\n".join(f"- {k}: {v}" for k, v in _CONTEXT_BRIEFS.items())
    pro_note = ", ".join(sorted(_CONTEXTS_WITH_PROFESSIONS))
    return f"""Ты — астролог-практик и копирайтер для приложения «Матрица Судьбы»
(метод Ладини). Пишешь словарные расшифровки арканов на 9 жизненных позиций.

Читатель — обычный человек, не эзотерик. Текст должен быть тёплым, конкретным,
человеческим, как от поддерживающего наставника. Без банальностей вроде
«вселенная даст» или «звёзды говорят», без жаргона («энергии», «вибрации»,
«эманации», «архетипы»).

АРКАН: {arcana_num} — {name}
КЛЮЧЕВЫЕ СМЫСЛЫ: {", ".join(keywords) if keywords else "—"}

Для каждого из 9 контекстов нужно дать три поля:
  • `meaning` — 60-90 слов. Связный абзац: как именно этот аркан проявляется
    на этой позиции. Обращайся на «вы».
  • `plus`    — 20-30 слов. Одно-два предложения: ресурсное, здоровое
    проявление. С чего начать «использовать» эту энергию.
  • `minus`   — 20-30 слов. Одно-два предложения: теневая, разрушительная
    сторона. На что обратить внимание, чтобы не сваливаться сюда.

Контексты ({pro_note} — ещё `professions`: 4-6 профессий через запятую):
{contexts_block}

КАК ПИСАТЬ:
- Без клише и «звёздных» оборотов.
- Конкретные образы: разговоры, работа, дом, отношения, бытовые ситуации.
- Каждый абзац самодостаточен — пользователь видит ОДИН из них, не все 9.
- Не повторяйся: характер аркана общий, но проявление в каждой сфере разное.

Верни результат через инструмент publish_arcana_meanings."""


async def _generate_one(client: Any, arcana_num: int) -> dict[str, dict[str, str]] | None:
    name = ARCANA_NAMES_RU[arcana_num]
    keywords = ARCANA_KEYWORDS_RU.get(arcana_num, [])

    from anthropic.types import ToolChoiceToolParam, ToolParam
    tools = cast(list[ToolParam], [_tool_schema()])
    tool_choice: ToolChoiceToolParam = {
        "type": "tool",
        "name": "publish_arcana_meanings",
    }
    message = await client.messages.create(
        model=_MODEL,
        max_tokens=4000,
        tools=tools,
        tool_choice=tool_choice,
        messages=[{"role": "user", "content": _build_prompt(arcana_num, name, keywords)}],
    )
    tool_input: dict[str, Any] | None = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            tool_input = getattr(block, "input", None)
            break
    if not isinstance(tool_input, dict):
        return None
    return {ctx: dict(tool_input.get(ctx) or {}) for ctx in CONTEXTS}


async def _existing_keys(session) -> set[tuple[int, str]]:
    """Set of (arcana_num, context) already present at gender='any'."""
    result = await session.execute(
        select(ArcanaMeaning.arcana_num, ArcanaMeaning.context).where(
            ArcanaMeaning.gender == "any"
        )
    )
    return {(row[0], row[1]) for row in result.all()}


async def main(
    *,
    dry_run: bool = False,
    missing_only: bool = False,
    wipe: bool = False,
) -> None:
    if not settings.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY missing — aborting", flush=True)
        sys.exit(1)

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async with AsyncSessionLocal() as session:
        if wipe and not dry_run:
            await session.execute(delete(ArcanaMeaning))
            await session.commit()
            print("Wiped arcana_meanings.", flush=True)

        existing: set[tuple[int, str]] = set()
        if missing_only and not dry_run:
            existing = await _existing_keys(session)
            print(f"Existing 'any' rows: {len(existing)}", flush=True)

        for arcana_num in range(1, 23):
            # In --missing-only mode, only skip if ALL 9 contexts already exist.
            if missing_only and {(arcana_num, c) for c in CONTEXTS}.issubset(existing):
                print(f"  [{arcana_num:02d}/22] {ARCANA_NAMES_RU[arcana_num]} — skipped (already seeded)", flush=True)
                continue

            print(f"  [{arcana_num:02d}/22] {ARCANA_NAMES_RU[arcana_num]}", end=" ", flush=True)
            data = await _generate_one(client, arcana_num)
            if not data:
                print("SKIPPED (no tool_use in reply)", flush=True)
                continue

            if dry_run:
                print("OK (dry-run)", flush=True)
                print(json.dumps(data, ensure_ascii=False, indent=2), flush=True)
                continue

            rows = []
            for ctx in CONTEXTS:
                fields = data.get(ctx) or {}
                rows.append({
                    "arcana_num": arcana_num,
                    "arcana_name": ARCANA_NAMES_RU[arcana_num],
                    "context": ctx,
                    "gender": "any",
                    "meaning": str(fields.get("meaning") or "").strip(),
                    "plus": str(fields.get("plus") or "").strip() or None,
                    "minus": str(fields.get("minus") or "").strip() or None,
                    "professions": (
                        str(fields.get("professions") or "").strip() or None
                        if ctx in _CONTEXTS_WITH_PROFESSIONS
                        else None
                    ),
                    "keywords": ARCANA_KEYWORDS_RU.get(arcana_num, []),
                })

            stmt = pg_insert(ArcanaMeaning).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_arcana_num_context_gender",
                set_=dict(
                    arcana_name=stmt.excluded.arcana_name,
                    meaning=stmt.excluded.meaning,
                    plus=stmt.excluded.plus,
                    minus=stmt.excluded.minus,
                    professions=stmt.excluded.professions,
                    keywords=stmt.excluded.keywords,
                ),
            )
            await session.execute(stmt)
            await session.commit()
            print("OK", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(
        main(
            dry_run="--dry-run" in args,
            missing_only="--missing-only" in args,
            wipe="--wipe" in args,
        )
    )
