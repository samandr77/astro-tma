"""Rank natal aspects so the UI can show a top-N list of the most
significant ones. Used by the new "Ключевые аспекты" block on the
Aspects tab.
"""

from __future__ import annotations

from typing import Any

ASPECT_BASE_WEIGHT: dict[str, int] = {
    "conjunction": 10,
    "opposition":  9,
    "square":      8,
    "trine":       7,
    "sextile":     5,
    "quincunx":    3,
}

PLANET_IMPORTANCE: dict[str, int] = {
    "sun": 5, "moon": 5,
    "ascendant": 5, "mc": 4,
    "mercury": 3, "venus": 3, "mars": 3,
    "jupiter": 3, "saturn": 3,
    "uranus": 2, "neptune": 2, "pluto": 2,
}

_PERSONAL_POINTS = {"sun", "moon", "ascendant", "mc"}


def _score(aspect: dict[str, Any]) -> float:
    p1 = (aspect.get("p1") or "").lower()
    p2 = (aspect.get("p2") or "").lower()
    asp = (aspect.get("aspect") or "").lower()
    orb = aspect.get("orb")
    try:
        orb = float(orb) if orb is not None else 6.0
    except (TypeError, ValueError):
        orb = 6.0

    score = float(ASPECT_BASE_WEIGHT.get(asp, 0))
    score += PLANET_IMPORTANCE.get(p1, 1)
    score += PLANET_IMPORTANCE.get(p2, 1)
    # Tighter orbs are stronger; +0..+6 bonus.
    score += max(0.0, 6.0 - orb)
    # Personal-point bonus.
    if p1 in _PERSONAL_POINTS or p2 in _PERSONAL_POINTS:
        score += 3.0
    return round(score, 2)


def rank_aspects(aspects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return aspects sorted by composite weight, decorated with ``key_score``."""
    ranked: list[dict[str, Any]] = []
    for a in aspects:
        ranked.append({**a, "key_score": _score(a)})
    ranked.sort(key=lambda x: x["key_score"], reverse=True)
    return ranked


def top_n_aspects(aspects: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    return rank_aspects(aspects)[:n]
