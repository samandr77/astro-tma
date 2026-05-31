"""
LLM-generated personalised descriptions for natal planets, houses and aspects.

Produces both a short blurb (shown in the in-app popup) and a compact full
paragraph (rendered in the downloadable PDF).
Result is cached by the caller — this module only calls the API.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from core.logging import get_logger
from services.astro.sign_cases import sign_ru
from services.llm_utils import first_text_block

log = get_logger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

from services.astro.planet_names import PLANET_RU as _PLANET_RU  # noqa: E402

# Iteration order for the per-planet description loop — only the 10 classical
# points; chart axes / nodes / Lilith come through aspects but aren't seeded
# as standalone descriptions.
_PLANET_ORDER = [
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
]

_ASPECT_RU: dict[str, str] = {
    "conjunction": "соединение",
    "sextile": "секстиль",
    "square": "квадрат",
    "trine": "трин",
    "opposition": "оппозиция",
    "quincunx": "квинконс",
}

def _normalise_sign(sign: str | None) -> str:
    return sign_ru(sign)


def _strip_code_fence(text: str) -> str:
    """Strip any leading/trailing ```/```json fence the model emits.
    Handles both balanced (both fences present) and unbalanced output."""
    text = text.strip()
    # Leading fence
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    # Trailing fence
    text = re.sub(r"\n?\s*```\s*$", "", text)
    return text.strip()


def _escape_unescaped_newlines_in_strings(raw: str) -> str:
    """Walk the JSON char-by-char and replace bare \\n inside string values
    with \\\\n. Handles the most common LLM mistake — emitting multi-line
    Russian text inside a JSON string without escaping the newlines."""
    out: list[str] = []
    in_string = False
    escape_next = False
    for ch in raw:
        if escape_next:
            out.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            out.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch == "\n":
            out.append("\\n")
            continue
        if in_string and ch == "\r":
            out.append("\\r")
            continue
        if in_string and ch == "\t":
            out.append("\\t")
            continue
        out.append(ch)
    return "".join(out)


def _safe_load_json(raw: str) -> Any:
    cleaned = _strip_code_fence(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try escaping bare newlines inside strings — the most common LLM failure.
    try:
        return json.loads(_escape_unescaped_newlines_in_strings(cleaned))
    except json.JSONDecodeError:
        pass
    # Fall back to extracting the first JSON object/array embedded in prose
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if not match:
        raise json.JSONDecodeError("no json-like content found", cleaned, 0)
    inner = match.group(1)
    try:
        return json.loads(inner)
    except json.JSONDecodeError:
        return json.loads(_escape_unescaped_newlines_in_strings(inner))


# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_planets_prompt(planets: dict[str, dict[str, Any]]) -> str:
    rows: list[str] = []
    for key in _PLANET_ORDER:
        p = planets.get(key)
        if not p:
            continue
        sign_nom = sign_ru(p.get("sign_ru") or p.get("sign"))
        sign_prep = sign_ru(p.get("sign_ru") or p.get("sign"), "prep")
        sign_gen = sign_ru(p.get("sign_ru") or p.get("sign"), "gen")
        house = p.get("house", "?")
        retro = " (ретроградный)" if p.get("retrograde") else ""
        rows.append(
            f"- {key}: {_PLANET_RU[key]} в {sign_prep} / в знаке {sign_gen}; "
            f"именительный: {sign_nom}; {house}-й дом{retro}"
        )

    count = len(rows)
    return f"""Ты — опытный астролог, пишешь персональные интерпретации натальной карты на русском языке.

Раздел PDF: «Планеты в знаках».
Положения планет ({count} штук):
{chr(10).join(rows)}

Для КАЖДОЙ из перечисленных планет напиши:
- "short" — компактное описание (2 предложения, ~35-55 слов): что эта планета в данном знаке означает для человека — характер, проявления в жизни, на что обратить внимание; дом упомяни только одним прикладным штрихом.
- "full" — полноценное описание (2-3 абзаца, ~140-190 слов): центр разбора — связка планета + знак. Раскрой характер, мотивацию, сильные стороны, уязвимости, отношения, работу/дела, привычки, бытовые проявления и один практический совет. Дом используй только в финальном предложении как персональное уточнение, не делай его главной темой.

Пиши тепло, конкретно, от второго лица («вы»). Не копируй чужие тексты. Избегай общих фраз вроде «вы творческий человек» без объяснения, как это видно в жизни. Используй правильные склонения: «Солнце в Скорпионе», но «в знаке Скорпиона». Без рекламы, markdown, заголовков и списков. Только обычные предложения и абзацы внутри строк.

Вызови инструмент submit_planet_descriptions РОВНО ОДИН РАЗ. В одном вызове укажи КАЖДУЮ из {count} планет как отдельный ключ верхнего уровня (например, "sun", "moon", "mercury", … "pluto"); значение каждого ключа — это объект с двумя полями short и full. Не пропускай ни одну планету."""


def _build_houses_prompt(houses: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for h in houses:
        num = h.get("number")
        if not num:
            continue
        sign_nom = sign_ru(h.get("sign_ru") or h.get("sign"))
        sign_prep = sign_ru(h.get("sign_ru") or h.get("sign"), "prep")
        rows.append(f"- Дом {num}: знак на куспиде — {sign_nom}; дом в {sign_prep}")

    count = len(rows)
    return f"""Ты — опытный астролог, пишешь персональные интерпретации натальной карты на русском языке.

Куспиды домов ({count} штук):
{chr(10).join(rows)}

Для КАЖДОГО дома напиши:
- "short" — компактное описание (2 предложения, ~35-55 слов): какую сферу жизни описывает этот дом, как знак на куспиде окрашивает её, ключевые проявления.
- "full" — полноценное описание (1-2 абзаца, ~90-130 слов): тема дома, стиль знака на куспиде, типичные жизненные сценарии, как это видно в характере и поведении, сильная сторона, точка внимания и короткий практический ориентир.

Пиши тепло, конкретно, от второго лица («вы»). Не копируй чужие тексты. Избегай общих фраз без жизненного проявления. Используй правильные склонения: «знак на куспиде — Овен», но «дом в Овне». Без markdown, без заголовков, без списков. Только обычные предложения.

Вызови инструмент submit_house_descriptions РОВНО ОДИН РАЗ. В одном вызове укажи КАЖДЫЙ из {count} домов как отдельный ключ верхнего уровня в виде строки с номером ("1", "2", …, "{count}"); значение каждого ключа — это объект с двумя полями short и full. Не пропускай ни один дом."""


def _build_aspects_prompt(aspects: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Returns (prompt, list_of_aspect_ids). Empty prompt + empty list if
    nothing was usable."""
    rows: list[str] = []
    aspect_keys: list[tuple[str, str, str]] = []
    for a in aspects:
        p1 = (a.get("p1") or "").lower()
        p2 = (a.get("p2") or "").lower()
        atype = (a.get("aspect") or "").lower()
        if not p1 or not p2 or not atype:
            continue
        if p1 not in _PLANET_RU or p2 not in _PLANET_RU:
            continue
        if atype not in _ASPECT_RU:
            continue
        orb = a.get("orb", 0)
        rows.append(
            f"- {p1}_{p2}_{atype}: {_PLANET_RU[p1]} — {_ASPECT_RU[atype]} — "
            f"{_PLANET_RU[p2]} (орб {float(orb):.1f}°)"
        )
        aspect_keys.append((p1, p2, atype))

    if not rows:
        return "", []

    aspect_ids = [f"{p1}_{p2}_{atype}" for p1, p2, atype in aspect_keys]
    count = len(rows)
    prompt = f"""Ты — опытный астролог, пишешь персональные интерпретации натальной карты на русском языке.

Аспекты между планетами ({count} штук):
{chr(10).join(rows)}

Для КАЖДОГО аспекта напиши:
- "short" — компактное описание (2 предложения, ~35-55 слов): как эти две планеты взаимодействуют, что человеку даёт или с чем приходится работать.
- "full" — полноценное описание (1-2 абзаца, ~110-160 слов): как именно взаимодействуют две планеты, гармония это или напряжение, какие темы жизни затронуты, как проявляется в характере, отношениях/делах и повторяющихся ситуациях, что является сильной стороной и где зона роста.

Пиши тепло, конкретно, от второго лица («вы»). Не копируй чужие тексты. Не ограничивайся фразой «планеты взаимодействуют»: объясни механизм и жизненный пример. Без markdown, без заголовков, без списков. Только обычные предложения.

Вызови инструмент submit_aspect_descriptions РОВНО ОДИН РАЗ. В одном вызове укажи КАЖДЫЙ из {count} аспектов как отдельный ключ верхнего уровня в формате "<планета1>_<планета2>_<аспект>" (например, "{aspect_ids[0]}"); значение каждого ключа — это объект с двумя полями short и full. Не пропускай ни один аспект."""
    return prompt, aspect_ids


# ── LLM call ──────────────────────────────────────────────────────────────────


def _entry_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "short": {"type": "string"},
            "full": {"type": "string"},
        },
        "required": ["short", "full"],
    }


def _planets_tool_schema(planets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Force the model to return entries only for the planets we actually
    have. Each value is an object with required `short`+`full` strings."""
    keys = [k for k in _PLANET_ORDER if k in planets]
    if not keys:
        keys = list(planets.keys())
    return {
        "type": "object",
        "properties": {k: _entry_schema() for k in keys},
        "required": keys,
    }


def _houses_tool_schema(houses: list[dict[str, Any]]) -> dict[str, Any]:
    nums = [str(h.get("number")) for h in houses if h.get("number")]
    return {
        "type": "object",
        "properties": {n: _entry_schema() for n in nums},
        "required": nums,
    }


def _aspects_tool_schema(aspect_ids: list[str]) -> dict[str, Any]:
    """Flat object keyed by aspect_id (e.g. "sun_moon_trine"). Matches the
    structure planets/houses already use, which the model handles better
    than nested arrays."""
    return {
        "type": "object",
        "properties": {aid: _entry_schema() for aid in aspect_ids},
        "required": aspect_ids,
    }


async def _call_tool(
    client: Any,
    prompt: str,
    tool_name: str,
    input_schema: dict[str, Any],
    max_tokens: int,
) -> dict[str, Any] | None:
    """Invoke the model with a forced tool call — the response's tool_use
    block carries an already-parsed dict matching `input_schema`. No JSON
    string handling needed on our side."""
    message = await client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        tools=[
            {
                "name": tool_name,
                "description": "Submit the requested descriptions.",
                "input_schema": input_schema,
            }
        ],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            return getattr(block, "input", None)
    return None


async def _call_llm(client: Any, prompt: str, max_tokens: int) -> str:
    """Legacy plain-text call — kept for any future free-form prompt."""
    message = await client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return first_text_block(message.content)


def _single_entry_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "short": {"type": "string"},
            "full": {"type": "string"},
        },
        "required": ["short", "full"],
    }


_STYLE_BRIEF = """КАК ПИСАТЬ:
- Живой разговорный язык, как будто рассказываешь хорошему знакомому про него самого.
- Конкретные образы из жизни: работа, отношения, привычки, разговоры, реакции.
- Без астрологического жаргона: ни «энергии», ни «вселенная», ни «архетипы», ни «эманации», ни «работа со страхами».
- Без банальностей вроде «вы — творческая натура».
- Не копируй чужие тексты; используй только общую структуру глубокого астрологического разбора.
- Следи за склонениями знаков: «в Скорпионе», но «в знаке Скорпиона».
- Обращайся на «вы», но по-человечески, не официально.
- Без markdown, без списков, без заголовков."""


def _planet_one_prompt(key: str, planet: dict[str, Any]) -> str:
    sign_nom = sign_ru(planet.get("sign_ru") or planet.get("sign"))
    sign_prep = sign_ru(planet.get("sign_ru") or planet.get("sign"), "prep")
    sign_gen = sign_ru(planet.get("sign_ru") or planet.get("sign"), "gen")
    house = planet.get("house", "?")
    retro = " (ретроградный)" if planet.get("retrograde") else ""
    return f"""Ты пишешь раздел PDF «Планеты в знаках» для популярного приложения с натальными картами. Читатель — обычный человек, не астролог.

Планета: {_PLANET_RU.get(key, key)} в {sign_prep}; форма «в знаке {sign_gen}»; именительный: {sign_nom}; {house}-й дом{retro}.
Важно: центр разбора — связка планета + знак. Дом используй только как короткое персональное уточнение ближе к концу, не смешивай весь текст с темой дома.

Вызови инструмент submit_entry с двумя полями:
- "short" (2 предложения, ~35-55 слов): что эта планета в данном знаке значит для человека — как проявляется в характере и в жизни, на что обратить внимание; дом упомяни только одним прикладным штрихом.
- "full" (2-3 абзаца, ~140-190 слов): подробный справочный текст как в классическом описании «планета в знаке»: характер, мотивации, сильные стороны, уязвимости, отношения, работа/дела, привычки, бытовые проявления и практический совет. Дом добавь только в финальном предложении как персональный акцент.

{_STYLE_BRIEF}"""


def _house_one_prompt(num: int, sign_name: str) -> str:
    sign_nom = sign_ru(sign_name)
    sign_prep = sign_ru(sign_name, "prep")
    return f"""Ты пишешь персональный разбор натальной карты для популярного приложения. Читатель — обычный человек, не астролог.

Дом: {num}-й, знак на куспиде — {sign_nom}; форма «дом в {sign_prep}».

Вызови инструмент submit_entry с двумя полями:
- "short" (2 предложения, ~35-55 слов): какую сферу жизни описывает этот дом, как знак на куспиде её окрашивает, ключевые проявления.
- "full" (1-2 абзаца, ~90-130 слов): тема дома подробнее, стиль знака на куспиде, типичные жизненные сценарии, как это видно в характере и поведении, сильная сторона, точка внимания и короткий практический ориентир.

{_STYLE_BRIEF}"""


def _aspect_one_prompt(p1: str, p2: str, atype: str) -> str:
    return f"""Ты пишешь персональный разбор натальной карты для популярного приложения. Читатель — обычный человек, не астролог.

Аспект: {_PLANET_RU.get(p1, p1)} — {_ASPECT_RU.get(atype, atype)} — {_PLANET_RU.get(p2, p2)}.

Вызови инструмент submit_entry с двумя полями:
- "short" (2 предложения, ~35-55 слов): как эти две темы взаимодействуют — что даёт человеку или с чем приходится работать.
- "full" (1-2 абзаца, ~110-160 слов): как именно сочетаются эти две темы, гармония это или трение, какие сферы жизни затронуты, как проявляется в характере, отношениях/делах и повторяющихся ситуациях, сильные стороны и зоны роста.

{_STYLE_BRIEF}"""


async def _one_entry(
    client: Any,
    prompt: str,
    sem: asyncio.Semaphore,
    max_tokens: int = 1536,
) -> dict[str, str]:
    """Single LLM call → dict with {short, full}. Semaphore-limited and
    auto-retries once on a 429 rate-limit response. Returns empty strings
    on permanent failure."""
    for attempt in range(2):
        async with sem:
            try:
                result = await _call_tool(
                    client,
                    prompt,
                    "submit_entry",
                    _single_entry_schema(),
                    max_tokens,
                )
                if isinstance(result, dict):
                    return {
                        "short": str(result.get("short", "")),
                        "full": str(result.get("full", "")),
                    }
                return {"short": "", "full": ""}
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                is_rate_limit = "429" in msg or "rate_limit" in msg.lower()
                if is_rate_limit and attempt == 0:
                    log.info("natal_descriptions.rate_limit_retry")
                    await asyncio.sleep(20)
                    continue
                log.warning("natal_descriptions.entry_failed", error=msg[:200])
                return {"short": "", "full": ""}
    return {"short": "", "full": ""}


def _chunked(items: list[Any], n: int) -> list[list[Any]]:
    """Split a list into fixed-size chunks (last chunk may be shorter)."""
    return [items[i : i + n] for i in range(0, len(items), n)]


async def _call_tool_chunk(
    client: Any,
    prompt: str,
    tool_name: str,
    keys: list[str],
    max_tokens: int,
    sem: asyncio.Semaphore,
) -> dict[str, dict[str, str]]:
    """Single batched LLM call → flat {key → {short, full}} dict. Retries
    once on 429. Returns empty dict on permanent failure."""
    schema = {
        "type": "object",
        "properties": {k: _entry_schema() for k in keys},
        "required": keys,
    }
    for attempt in range(2):
        async with sem:
            try:
                result = await _call_tool(
                    client, prompt, tool_name, schema, max_tokens,
                )
                if not isinstance(result, dict):
                    return {}
                out: dict[str, dict[str, str]] = {}
                for k, v in result.items():
                    if isinstance(v, dict):
                        out[str(k)] = {
                            "short": str(v.get("short", "")),
                            "full": str(v.get("full", "")),
                        }
                return out
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                is_rate_limit = "429" in msg or "rate_limit" in msg.lower()
                if is_rate_limit and attempt == 0:
                    log.info("natal_descriptions.batch_rate_limit_retry")
                    await asyncio.sleep(20)
                    continue
                log.warning(
                    "natal_descriptions.batch_failed",
                    tool=tool_name, keys=keys, error=msg[:200],
                )
                return {}
    return {}


# Per-chunk cap of items in a single LLM call. 5 keeps Haiku's schema
# adherence reliable while still cutting the per-chart call count from
# ~30 individual calls down to ~6 batches.
_BATCH_SIZE = 5
# Output budget per batch — compact copy: 5 entries fit under ~1400 tokens,
# with room for tool-call JSON structure.
_BATCH_MAX_TOKENS = 2600


async def generate_natal_descriptions(
    planets: dict[str, dict[str, Any]],
    houses: list[dict[str, Any]],
    aspects: list[dict[str, Any]],
    api_key: str,
) -> dict[str, Any]:
    """Batched LLM generation: each tool call covers up to 5 items at once,
    cutting the per-chart call count from ~30 to ~6 (and the cost
    proportionally). Reliable for Haiku — 5 keys is well within its schema
    adherence window. Cached forever per chart so the cost is paid once."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    # Anthropic free-tier rate limit is 50 RPM with low concurrent-conn cap.
    # 3 in flight is plenty for 6-7 batched calls and keeps us under both.
    sem = asyncio.Semaphore(3)

    # ── Planets ─────────────────────────────────────────────────────────
    planet_items = [(k, p) for k in _PLANET_ORDER if (p := planets.get(k))]
    planet_chunks = _chunked(planet_items, _BATCH_SIZE)
    planet_tasks = []
    for chunk in planet_chunks:
        chunk_dict = dict(chunk)
        prompt = _build_planets_prompt(chunk_dict)
        keys = [k for k, _ in chunk]
        planet_tasks.append(
            _call_tool_chunk(
                client, prompt, "submit_planet_descriptions",
                keys, _BATCH_MAX_TOKENS, sem,
            )
        )

    # ── Houses ──────────────────────────────────────────────────────────
    house_items: list[dict[str, Any]] = []
    for h in houses:
        num = h.get("number")
        if not num:
            continue
        house_items.append({
            "number": int(num),
            "sign_ru": _normalise_sign(h.get("sign_ru") or h.get("sign")),
        })
    house_chunks = _chunked(house_items, _BATCH_SIZE)
    house_tasks = []
    for chunk in house_chunks:
        prompt = _build_houses_prompt(chunk)
        keys = [str(h["number"]) for h in chunk]
        house_tasks.append(
            _call_tool_chunk(
                client, prompt, "submit_house_descriptions",
                keys, _BATCH_MAX_TOKENS, sem,
            )
        )

    # ── Aspects ─────────────────────────────────────────────────────────
    aspect_items: list[dict[str, Any]] = []
    aspect_ids_lookup: dict[str, tuple[str, str, str]] = {}
    for a in aspects:
        p1 = (a.get("p1") or "").lower()
        p2 = (a.get("p2") or "").lower()
        atype = (a.get("aspect") or "").lower()
        if not (
            p1 and p2 and atype
            and p1 in _PLANET_RU and p2 in _PLANET_RU
            and atype in _ASPECT_RU
        ):
            continue
        aid = f"{p1}_{p2}_{atype}"
        aspect_items.append({
            "p1": p1, "p2": p2, "aspect": atype, "orb": a.get("orb", 0),
        })
        aspect_ids_lookup[aid] = (p1, p2, atype)
    aspect_chunks = _chunked(aspect_items, _BATCH_SIZE)
    aspect_tasks = []
    for chunk in aspect_chunks:
        prompt, chunk_ids = _build_aspects_prompt(chunk)
        if not chunk_ids:
            continue
        aspect_tasks.append(
            _call_tool_chunk(
                client, prompt, "submit_aspect_descriptions",
                chunk_ids, _BATCH_MAX_TOKENS, sem,
            )
        )

    # Fire everything in parallel — semaphore caps actual concurrency.
    all_results = await asyncio.gather(
        *planet_tasks, *house_tasks, *aspect_tasks, return_exceptions=False,
    )

    p_n = len(planet_tasks)
    h_n = len(house_tasks)
    planet_results = all_results[:p_n]
    house_results = all_results[p_n : p_n + h_n]
    aspect_results = all_results[p_n + h_n :]

    out: dict[str, Any] = {"planets": {}, "houses": {}, "aspects": []}

    for chunk_dict in planet_results:
        for key, entry in chunk_dict.items():
            if entry.get("short") or entry.get("full"):
                out["planets"][key] = entry

    for chunk_dict in house_results:
        for key, entry in chunk_dict.items():
            if entry.get("short") or entry.get("full"):
                out["houses"][key] = entry

    for chunk_dict in aspect_results:
        for aid, entry in chunk_dict.items():
            triple = aspect_ids_lookup.get(aid)
            if not triple:
                continue
            if entry.get("short") or entry.get("full"):
                p1, p2, atype = triple
                out["aspects"].append(
                    {"p1": p1, "p2": p2, "type": atype, **entry}
                )

    log.info(
        "natal_descriptions.done",
        planets=len(out["planets"]),
        houses=len(out["houses"]),
        aspects=len(out["aspects"]),
        batches=len(planet_tasks) + len(house_tasks) + len(aspect_tasks),
    )
    return out
