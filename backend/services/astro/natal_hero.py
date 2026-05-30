"""Per-tab "hero info" builders for the Natal screen.

Each tab (Стихии / Планеты / Дома / Аспекты) gets a tiny `{headline, subline}`
payload that the frontend renders in place of the old decorative orbits.
Pure formatting; no LLM, no DB access.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.astro.dominants import ELEMENT_RU

HARMONIOUS = {"trine", "sextile", "conjunction"}
CHALLENGING = {"square", "opposition"}

_PLANET_RU: dict[str, str] = {
    "sun": "Солнце", "moon": "Луна", "mercury": "Меркурий",
    "venus": "Венера", "mars": "Марс", "jupiter": "Юпитер",
    "saturn": "Сатурн", "uranus": "Уран",
    "neptune": "Нептун", "pluto": "Плутон",
    "ascendant": "Асцендент", "mc": "MC",
}

_ASPECT_RU: dict[str, str] = {
    "conjunction": "соединение", "opposition": "оппозиция",
    "trine": "трин", "square": "квадрат",
    "sextile": "секстиль", "quincunx": "квинконс",
}

_HOUSE_TOPICS_RU: dict[int, str] = {
    1: "личности", 2: "финансах", 3: "общении", 4: "доме",
    5: "творчестве", 6: "работе", 7: "партнёрстве", 8: "переменах",
    9: "философии", 10: "карьере", 11: "сообществе", 12: "внутренней жизни",
}

_ELEMENT_TRAIT: dict[str, str] = {
    "fire":  "Активная карта",
    "earth": "Устойчивая карта",
    "air":   "Подвижная карта",
    "water": "Чувствующая карта",
}


def _plural_planets(n: int) -> str:
    if n == 1:
        return "планета"
    if 2 <= n <= 4:
        return "планеты"
    return "планет"


def _plural_retro(n: int) -> str:
    if n == 1:
        return "ретроградная"
    if 2 <= n <= 4:
        return "ретроградные"
    return "ретроградных"


def build_elements_hero(dominants: Mapping[str, Any]) -> dict[str, str]:
    el = dominants["elements"]
    total = el["fire"] + el["earth"] + el["air"] + el["water"]
    pct = int(round(el[el["dominant"]] / total * 100)) if total else 0
    dominant_ru = ELEMENT_RU[el["dominant"]].lower()
    trait = _ELEMENT_TRAIT.get(el["dominant"], "")
    subline = f"{trait} · {pct}%" if trait else f"{pct}%"
    return {
        "headline": f"Доминирует {dominant_ru}",
        "subline": subline,
    }


def build_planets_hero(
    planets: dict[str, Any],
    dominants: Mapping[str, Any],
) -> dict[str, str]:
    retro = dominants.get("retrograde_planets") or []
    n_retro = len(retro)
    signs = {
        (p.get("sign") or "").lower()
        for p in planets.values()
        if isinstance(p, dict) and p.get("sign")
    }
    n_signs = len(signs)
    parts: list[str] = []
    if n_retro:
        parts.append(f"{n_retro} {_plural_retro(n_retro)}")
    parts.append(f"в {n_signs} знаках")
    return {
        "headline": f"Доминирует {dominants['planet']['planet_ru']}",
        "subline": " · ".join(parts),
    }


def build_houses_hero(planets: dict[str, Any]) -> dict[str, str]:
    occupancy: dict[int, int] = {i: 0 for i in range(1, 13)}
    for p in planets.values():
        if not isinstance(p, dict):
            continue
        h = p.get("house")
        if isinstance(h, int) and 1 <= h <= 12:
            occupancy[h] += 1

    if max(occupancy.values()) == 0:
        return {
            "headline": "12 домов",
            "subline": "Карта вашей жизни по сферам",
        }

    dominant_house, count = max(occupancy.items(), key=lambda x: x[1])
    empty_count = sum(1 for v in occupancy.values() if v == 0)
    topic = _HOUSE_TOPICS_RU.get(dominant_house, "")
    parts = [f"{count} {_plural_planets(count)} в {topic}"] if topic else [f"{count} {_plural_planets(count)}"]
    if empty_count:
        parts.append(f"{empty_count} пустых")
    return {
        "headline": f"Загружен {dominant_house}-й дом",
        "subline": " · ".join(parts),
    }


def build_aspects_hero(
    aspects: list[dict[str, Any]],
    key_aspects: list[dict[str, Any]],
) -> dict[str, str]:
    harm = sum(1 for a in aspects if (a.get("aspect") or "").lower() in HARMONIOUS)
    chal = sum(1 for a in aspects if (a.get("aspect") or "").lower() in CHALLENGING)
    headline = f"{harm} гармоничных · {chal} напряжённых"

    if not key_aspects:
        return {"headline": headline, "subline": ""}

    top = key_aspects[0]
    p1 = _PLANET_RU.get((top.get("p1") or "").lower(), top.get("p1", ""))
    p2 = _PLANET_RU.get((top.get("p2") or "").lower(), top.get("p2", ""))
    asp = _ASPECT_RU.get((top.get("aspect") or "").lower(), top.get("aspect", ""))
    try:
        orb = float(top.get("orb", 0))
    except (TypeError, ValueError):
        orb = 0.0
    return {
        "headline": headline,
        "subline": f"Самый тесный: {p1} {asp} {p2} ({orb:.1f}°)",
    }
