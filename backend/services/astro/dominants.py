"""Compute dominant element / modality / planet for a natal chart.

Used to power the "Стихии" tab and per-tab hero info on the Natal screen.
Replaces the old 3-point (Sun/Moon/Asc) element count with a proper
weighted scan over all 10 planets + the Ascendant.
"""

from __future__ import annotations

from typing import Any, TypedDict

# Standard mass-market astrology weights. Asc is heaviest because it's the
# personal axis; luminaries next; personals; socials; outers (least personal).
PLANET_WEIGHTS: dict[str, float] = {
    "ascendant": 4.0,
    "sun":       3.0,
    "moon":      3.0,
    "mercury":   2.0,
    "venus":     2.0,
    "mars":      2.0,
    "jupiter":   1.5,
    "saturn":    1.5,
    "uranus":    1.0,
    "neptune":   1.0,
    "pluto":     1.0,
}

SIGN_ELEMENT: dict[str, str] = {
    "aries": "fire", "leo": "fire", "sagittarius": "fire",
    "taurus": "earth", "virgo": "earth", "capricorn": "earth",
    "gemini": "air", "libra": "air", "aquarius": "air",
    "cancer": "water", "scorpio": "water", "pisces": "water",
}

SIGN_MODALITY: dict[str, str] = {
    "aries": "cardinal", "cancer": "cardinal",
    "libra": "cardinal", "capricorn": "cardinal",
    "taurus": "fixed", "leo": "fixed",
    "scorpio": "fixed", "aquarius": "fixed",
    "gemini": "mutable", "virgo": "mutable",
    "sagittarius": "mutable", "pisces": "mutable",
}

# Traditional rulerships only (no Pluto/Uranus/Neptune rulers). Sufficient
# for v1 — adding modern rulers can come later behind a flag.
SIGN_RULER: dict[str, str] = {
    "aries": "mars", "taurus": "venus", "gemini": "mercury",
    "cancer": "moon", "leo": "sun", "virgo": "mercury",
    "libra": "venus", "scorpio": "mars", "sagittarius": "jupiter",
    "capricorn": "saturn", "aquarius": "saturn", "pisces": "jupiter",
}

ELEMENT_RU: dict[str, str] = {
    "fire": "Огонь",
    "earth": "Земля",
    "air": "Воздух",
    "water": "Вода",
}

MODALITY_RU: dict[str, str] = {
    "cardinal": "Кардинальная",
    "fixed":    "Фиксированная",
    "mutable":  "Мутабельная",
}

PLANET_RU_NAME: dict[str, str] = {
    "sun": "Солнце", "moon": "Луна", "mercury": "Меркурий",
    "venus": "Венера", "mars": "Марс", "jupiter": "Юпитер",
    "saturn": "Сатурн", "uranus": "Уран",
    "neptune": "Нептун", "pluto": "Плутон",
}

_OUTER_PLANETS = ("mercury", "venus", "mars", "jupiter",
                  "saturn", "uranus", "neptune", "pluto")


class ElementsDistribution(TypedDict, total=False):
    fire: float
    earth: float
    air: float
    water: float
    dominant: str
    dominant_ru: str
    deficient: str | None
    deficient_ru: str | None


class ModalitiesDistribution(TypedDict, total=False):
    cardinal: float
    fixed: float
    mutable: float
    dominant: str
    dominant_ru: str


class DominantPlanet(TypedDict):
    planet: str
    planet_ru: str
    score: float
    reason: str


class NatalDominants(TypedDict):
    elements: ElementsDistribution
    modalities: ModalitiesDistribution
    planet: DominantPlanet
    retrograde_planets: list[str]


def compute_dominants(
    planets: dict[str, dict[str, Any]],
    ascendant_sign: str | None,
) -> NatalDominants:
    """Compute element / modality / planet dominants for a chart.

    ``planets`` is the chart_data["planets"] dict; each value has at least
    ``sign`` (capitalized or lowercased) and ``house`` (1-12), ``retrograde``.
    ``ascendant_sign`` is the chart.ascendant_sign string (or None when
    birth time is unknown — in which case ASC weight is dropped).
    """
    elements = {"fire": 0.0, "earth": 0.0, "air": 0.0, "water": 0.0}
    modalities = {"cardinal": 0.0, "fixed": 0.0, "mutable": 0.0}

    if ascendant_sign:
        asc = ascendant_sign.lower()
        if asc in SIGN_ELEMENT:
            elements[SIGN_ELEMENT[asc]] += PLANET_WEIGHTS["ascendant"]
            modalities[SIGN_MODALITY[asc]] += PLANET_WEIGHTS["ascendant"]

    for key in ("sun", "moon", *_OUTER_PLANETS):
        p = planets.get(key)
        if not p:
            continue
        sign = (p.get("sign") or "").lower()
        weight = PLANET_WEIGHTS.get(key, 1.0)
        if sign in SIGN_ELEMENT:
            elements[SIGN_ELEMENT[sign]] += weight
            modalities[SIGN_MODALITY[sign]] += weight

    dominant_el = max(elements.items(), key=lambda x: x[1])[0]
    el_total = sum(elements.values()) or 1
    deficient_el = next(
        (k for k, v in elements.items() if v == 0 or v / el_total < 0.1),
        None,
    )
    dominant_mod = max(modalities.items(), key=lambda x: x[1])[0]

    dominant_planet = _compute_dominant_planet(planets, ascendant_sign)

    retrograde = [
        key for key in _OUTER_PLANETS
        if planets.get(key, {}).get("retrograde")
    ]

    return {
        "elements": {
            "fire": elements["fire"],
            "earth": elements["earth"],
            "air": elements["air"],
            "water": elements["water"],
            "dominant": dominant_el,
            "dominant_ru": ELEMENT_RU[dominant_el],
            "deficient": deficient_el,
            "deficient_ru": ELEMENT_RU.get(deficient_el) if deficient_el else None,
        },
        "modalities": {
            "cardinal": modalities["cardinal"],
            "fixed": modalities["fixed"],
            "mutable": modalities["mutable"],
            "dominant": dominant_mod,
            "dominant_ru": MODALITY_RU[dominant_mod],
        },
        "planet": dominant_planet,
        "retrograde_planets": retrograde,
    }


def _compute_dominant_planet(
    planets: dict[str, dict[str, Any]],
    ascendant_sign: str | None,
) -> DominantPlanet:
    """Composite score for "dominant planet":

    - +5 if it rules the Ascendant
    - +3 per ruler-of-luminary (Sun or Moon)
    - +2 per angular house placement (1/4/7/10)
    - +1 if in own sign (essential dignity)

    Returns the planet with the highest score and a human-readable reason.
    """
    scores: dict[str, float] = {k: 0.0 for k in PLANET_WEIGHTS if k != "ascendant"}
    reasons: dict[str, list[str]] = {k: [] for k in scores}

    if ascendant_sign:
        asc = ascendant_sign.lower()
        ruler = SIGN_RULER.get(asc)
        if ruler and ruler in scores:
            scores[ruler] += 5
            reasons[ruler].append("управляет вашим Асцендентом")

    for lum in ("sun", "moon"):
        p = planets.get(lum, {}) or {}
        sign = (p.get("sign") or "").lower()
        ruler = SIGN_RULER.get(sign)
        if ruler and ruler in scores:
            scores[ruler] += 3
            reasons[ruler].append(
                f"управляет вашим {PLANET_RU_NAME.get(lum, lum)}м"
                if lum == "sun"
                else f"управляет вашей {PLANET_RU_NAME.get(lum, lum)}"
            )

    for key, p in planets.items():
        if key not in scores or not isinstance(p, dict):
            continue
        house = p.get("house", 0)
        if isinstance(house, int) and house in (1, 4, 7, 10):
            scores[key] += 2
            reasons[key].append(f"в угловом доме ({house}-й)")
        sign = (p.get("sign") or "").lower()
        if SIGN_RULER.get(sign) == key:
            scores[key] += 1
            reasons[key].append("в своём знаке")

    dominant_key = max(scores.items(), key=lambda x: x[1])[0]
    reason_text = "; ".join(reasons[dominant_key]) or "по совокупности факторов"
    return {
        "planet": dominant_key,
        "planet_ru": PLANET_RU_NAME.get(dominant_key, dominant_key.title()),
        "score": round(scores[dominant_key], 1),
        "reason": reason_text,
    }
