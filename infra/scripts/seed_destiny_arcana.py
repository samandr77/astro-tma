#!/usr/bin/env python3
"""
Seed 22 arcana × 9 contexts = 198 text blocks into the `arcana_meanings`
table for the Destiny Matrix feature.

Each block is ~50-80 words of practical, on-tone description for one
arcana in one of these life contexts:
    personality, talents, purpose, parental, ancestral,
    relationships, finance, material_karma, karmic_tail

Generates content via Claude Haiku (one batched call per arcana with all
9 contexts in a single JSON tool-call). At Haiku 4.5 rates this costs
about $3-5 in total and takes ~5-10 minutes.

Run:
    docker compose exec backend python infra/scripts/seed_destiny_arcana.py
    # or, idempotently, only for arcana missing rows:
    docker compose exec backend python infra/scripts/seed_destiny_arcana.py --missing-only

Pass `--dry-run` to print to stdout instead of writing to DB.
"""

import asyncio
import json
import os
import sys
from typing import Any

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


_CONTEXT_HEADERS = {
    "personality": "ЛИЧНОСТЬ (характер, портрет, зона комфорта — позиция центра/портрета)",
    "talents": "ТАЛАНТЫ (высшая суть, что вдохновляет, зона роста — позиция месяца/верха ромба)",
    "purpose": "ПРЕДНАЗНАЧЕНИЕ (миссия, вектор проработки — ЛП/СП/ДП/ПЛ)",
    "parental": "ДЕТСКО-РОДИТЕЛЬСКИЙ (зачем пришёл от родителей, задача, типичные ошибки)",
    "ancestral": "РОДОВАЯ ПРОГРАММА (что транслирует род — таланты сверху, карма снизу)",
    "relationships": "ОТНОШЕНИЯ (какого партнёра притягиваешь — в плюсе и в минусе)",
    "finance": "ФИНАНСЫ (откуда деньги, подходящие профессии, риски с деньгами)",
    "material_karma": "МАТЕРИАЛЬНАЯ КАРМА (прошлый опыт, подсказка по профессии, что уже есть как ресурс)",
    "karmic_tail": "КАРМИЧЕСКИЙ ХВОСТ (главный кармический урок, что прорабатывать в этой жизни)",
}


def _build_prompt(arcana_num: int, arcana_name: str, keywords: list[str]) -> str:
    contexts_block = "\n".join(
        f"- {key}: {label}" for key, label in _CONTEXT_HEADERS.items()
    )
    return f"""Ты пишешь словарь интерпретаций аркана для приложения «Матрица Судьбы».
Читатели — обычные люди, не эзотерики. Текст должен быть тёплым, конкретным,
человеческим, без банальностей вроде «вселенная даст» или «звёзды говорят».

АРКАН: {arcana_num} — {arcana_name}
КЛЮЧЕВЫЕ СМЫСЛЫ: {", ".join(keywords)}

Напиши **по одному короткому абзацу (50-80 слов, 3-4 предложения)** для
каждого из 9 жизненных контекстов:
{contexts_block}

КАК ПИСАТЬ:
- Обращайся на «вы», по-человечески, без официоза.
- Конкретные образы: разговоры, работа, отношения, бытовые ситуации.
- Без жаргона: ни «энергии», ни «вибрации», ни «эманации», ни «архетипы».
- Без клише: ни «звёзды благоволят», ни «судьба ведёт».
- Каждый абзац самодостаточен — пользователь видит ОДИН из них, не все 9.

Верни ТОЛЬКО валидный JSON без markdown-обёрток в формате:
{{
  "personality": "...",
  "talents": "...",
  "purpose": "...",
  "parental": "...",
  "ancestral": "...",
  "relationships": "...",
  "finance": "...",
  "material_karma": "...",
  "karmic_tail": "..."
}}"""


async def _generate_one(client: Any, arcana_num: int) -> dict[str, str] | None:
    name = ARCANA_NAMES_RU[arcana_num]
    keywords = ARCANA_KEYWORDS_RU.get(arcana_num, [])
    prompt = _build_prompt(arcana_num, name, keywords)

    message = await client.messages.create(
        model=_MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in message.content if hasattr(b, "text")).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0] if "\n" in raw else raw
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[arcana {arcana_num}] JSON parse failed: {e}\nRaw: {raw[:200]}…")
        return None
    return {ctx: str(parsed.get(ctx, "")).strip() for ctx in CONTEXTS}


async def _existing_arcana_nums(session) -> set[int]:
    result = await session.execute(select(ArcanaMeaning.arcana_num).distinct())
    return {row[0] for row in result.all()}


async def main(dry_run: bool = False, missing_only: bool = False, wipe: bool = False) -> None:
    if not settings.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY missing — aborting")
        sys.exit(1)

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async with AsyncSessionLocal() as session:
        if wipe and not dry_run:
            await session.execute(delete(ArcanaMeaning))
            await session.commit()
            print("Wiped arcana_meanings.")

        existing: set[int] = set()
        if missing_only and not dry_run:
            existing = await _existing_arcana_nums(session)
            print(f"Existing arcana already seeded: {sorted(existing)}")

        targets = [n for n in range(1, 23) if n not in existing]
        print(f"Generating {len(targets)} arcana × 9 contexts...")

        for arcana_num in targets:
            print(f"  [{arcana_num:02d}/22] {ARCANA_NAMES_RU[arcana_num]}", end=" ", flush=True)
            contexts = await _generate_one(client, arcana_num)
            if not contexts:
                print("SKIPPED (parse failure)")
                continue

            if dry_run:
                print("OK (dry-run)")
                print(json.dumps(contexts, ensure_ascii=False, indent=2))
                continue

            rows = []
            for ctx, meaning in contexts.items():
                rows.append({
                    "arcana_num": arcana_num,
                    "arcana_name": ARCANA_NAMES_RU[arcana_num],
                    "context": ctx,
                    "meaning": meaning,
                    "keywords": ARCANA_KEYWORDS_RU.get(arcana_num, []),
                })

            stmt = pg_insert(ArcanaMeaning).values(rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_arcana_num_context",
                set_=dict(
                    arcana_name=stmt.excluded.arcana_name,
                    meaning=stmt.excluded.meaning,
                    keywords=stmt.excluded.keywords,
                ),
            )
            await session.execute(stmt)
            await session.commit()
            print("OK")

    print("\nDone.")


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(
        main(
            dry_run="--dry-run" in args,
            missing_only="--missing-only" in args,
            wipe="--wipe" in args,
        )
    )
