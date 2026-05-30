"""
Daily transit calculation — current sky vs natal chart.
Used to personalise horoscopes beyond generic sun-sign text.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from kerykeion import AstrologicalSubjectFactory, SynastryAspects

from core.logging import get_logger
from services.astro.natal import _PLANET_ATTRS

log = get_logger(__name__)

# Tight orbs for transits (stricter than natal)
TRANSIT_ORBS: dict[str, float] = {
    "conjunction": 3.0,
    "opposition": 3.0,
    "square": 2.5,
    "trine": 2.5,
    "sextile": 2.0,
}

# Weight by significance (used to sort which transits matter most)
PLANET_WEIGHT: dict[str, int] = {
    "sun": 10, "moon": 9, "mercury": 6, "venus": 7, "mars": 8,
    "jupiter": 5, "saturn": 7, "uranus": 3, "neptune": 2, "pluto": 2,
}

ASPECT_WEIGHT: dict[str, int] = {
    "conjunction": 10, "opposition": 8, "square": 7,
    "trine": 6, "sextile": 4,
}


def get_current_sky(dt: datetime | None = None) -> dict[str, Any]:
    """Return current planetary positions as a plain dict."""
    dt = dt or datetime.now(UTC)
    subject = AstrologicalSubjectFactory.from_birth_data(
        name="_transit",
        year=dt.year, month=dt.month, day=dt.day,
        hour=dt.hour, minute=dt.minute,
        lat=0.0, lng=0.0, tz_str="UTC",
        online=False,
    )
    return {
        attr: {
            "sign": getattr(subject, attr).sign,
            "degree": round(getattr(subject, attr).abs_pos, 4),
            "retrograde": bool(getattr(subject, attr).retrograde),
        }
        for attr in _PLANET_ATTRS
    }


def calculate_transits(
    birth_dt: datetime,
    lat: float,
    lng: float,
    tz_str: str,
    dt: datetime | None = None,
    birth_time_known: bool = True,
) -> list[dict[str, Any]]:
    """
    Find significant transit aspects to natal chart.
    Returns list sorted by significance (highest-weight first).
    """
    dt = dt or datetime.now(UTC)
    hour = birth_dt.hour if birth_time_known else 12
    minute = birth_dt.minute if birth_time_known else 0

    natal_subject = AstrologicalSubjectFactory.from_birth_data(
        name="_natal",
        year=birth_dt.year, month=birth_dt.month, day=birth_dt.day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        online=False,
    )
    transit_subject = AstrologicalSubjectFactory.from_birth_data(
        name="_current",
        year=dt.year, month=dt.month, day=dt.day,
        hour=dt.hour, minute=dt.minute,
        lat=0.0, lng=0.0, tz_str="UTC",
        online=False,
    )

    synastry = SynastryAspects(natal_subject, transit_subject)
    results: list[dict[str, Any]] = []

    for aspect in synastry.all_aspects:
        # Kerykeion v5 exposes "aspect"; older versions used "aspect_name".
        aspect_raw = getattr(aspect, "aspect", None) or getattr(aspect, "aspect_name", "")
        if callable(aspect_raw):
            aspect_raw = aspect_raw()
        aspect_name = str(aspect_raw).lower()
        if aspect_name not in TRANSIT_ORBS:
            continue
        if abs(aspect.orbit) > TRANSIT_ORBS[aspect_name]:
            continue

        weight = (
            PLANET_WEIGHT.get(aspect.p1_name.lower(), 1)
            + ASPECT_WEIGHT.get(aspect_name, 1)
        )

        # Detect retrograde on the transit subject planet.
        t_attr = aspect.p2_name.lower()
        t_obj = getattr(transit_subject, t_attr, None)
        transit_retro = bool(getattr(t_obj, "retrograde", False)) if t_obj else False

        # Determine applying/separating. Prefer Kerykeion's native hints:
        #   aspect_movement: "Applying" | "Separating" | "Static"
        # Fallback: sign of p2_speed (transit planet) vs retro flag.
        applying: bool | None = None
        movement = str(getattr(aspect, "aspect_movement", "") or "").lower()
        if movement == "applying":
            applying = True
        elif movement == "separating":
            applying = False
        elif movement == "static":
            p2_speed = getattr(aspect, "p2_speed", 0.0) or 0.0
            if p2_speed != 0:
                applying = bool(p2_speed > 0) and not transit_retro

        results.append({
            "transit_planet": aspect.p2_name,
            "natal_planet": aspect.p1_name,
            "aspect": aspect_name,
            "orb": round(abs(aspect.orbit), 2),
            "weight": weight,
            "transit_retrograde": transit_retro,
            "applying": applying,
        })

    results.sort(key=lambda x: x["weight"], reverse=True)
    log.debug("transits.calculated", count=len(results), date=dt.date().isoformat())
    return results[:10]  # top 10 most significant


def build_energy_scores(transits: list[dict[str, Any]], base_sign: str) -> dict[str, int]:
    """
    Derive love / career / health / luck scores from active transits.
    Returns values 0–100. Used for the progress bars in the UI.
    """
    base = 55  # neutral baseline

    # Sign-based modifiers (static component)
    sign_mod: dict[str, dict[str, int]] = {
        "aries":       {"love": -2, "career": 5, "health": 5, "luck": 3},
        "taurus":      {"love": 5,  "career": 2, "health": 3, "luck": 2},
        "gemini":      {"love": 2,  "career": 5, "health": -2,"luck": 3},
        "cancer":      {"love": 8,  "career": -2,"health": 3, "luck": 0},
        "leo":         {"love": 5,  "career": 8, "health": 3, "luck": 5},
        "virgo":       {"love": -2, "career": 8, "health": 5, "luck": 2},
        "libra":       {"love": 8,  "career": 2, "health": 0, "luck": 5},
        "scorpio":     {"love": 5,  "career": 3, "health": -3,"luck": 2},
        "sagittarius": {"love": 3,  "career": 3, "health": 5, "luck": 8},
        "capricorn":   {"love": -3, "career": 10,"health": 2, "luck": 3},
        "aquarius":    {"love": 2,  "career": 5, "health": 0, "luck": 5},
        "pisces":      {"love": 5,  "career": -2,"health": 2, "luck": 3},
    }

    mods = sign_mod.get(base_sign.lower(), {})
    scores = {
        "love":   base + mods.get("love", 0),
        "career": base + mods.get("career", 0),
        "health": base + mods.get("health", 0),
        "luck":   base + mods.get("luck", 0),
    }

    # Transit-based adjustments
    _LOVE_PLANETS = {"venus", "moon"}
    _CAREER_PLANETS = {"saturn", "jupiter", "mars", "sun"}
    _HEALTH_PLANETS = {"mars", "sun", "moon"}
    _LUCK_PLANETS = {"jupiter", "sun"}

    _POSITIVE_ASPECTS = {"trine", "sextile", "conjunction"}
    _NEGATIVE_ASPECTS = {"square", "opposition"}

    for t in transits:
        tp = t["transit_planet"].lower()
        aspect = t["aspect"]
        delta = 5 if aspect in _POSITIVE_ASPECTS else -5
        if tp in _LOVE_PLANETS:    scores["love"]   += delta
        if tp in _CAREER_PLANETS:  scores["career"] += delta
        if tp in _HEALTH_PLANETS:  scores["health"] += delta
        if tp in _LUCK_PLANETS:    scores["luck"]   += delta

    # Clamp 20–95
    return {k: max(20, min(95, v)) for k, v in scores.items()}


# ── Week / Month event scan ───────────────────────────────────────────────────

# Tighter orb thresholds for period events — only show truly near-exact aspects
# on the week / month timeline.
_PERIOD_PEAK_ORB: float = 1.5
_PERIOD_SCAN_ORB: dict[str, float] = {
    "conjunction": 2.0,
    "opposition": 2.0,
    "square": 1.8,
    "trine": 1.8,
    "sextile": 1.5,
}

# Skip the Moon's ingresses for the week view — it changes sign every ~2.5
# days, which would dominate the timeline. Keep them for the month view.
_FAST_MOON_PLANETS = {"moon"}


def calculate_period_events(
    birth_dt: datetime,
    lat: float,
    lng: float,
    tz_str: str,
    start_date: date,
    days: int,
    *,
    birth_time_known: bool = True,
    top_n: int | None = None,
    include_moon_ingresses: bool = False,
) -> list[dict[str, Any]]:
    """Walk `days` calendar days starting from `start_date` and collect:

    - aspect peaks: per (transit_planet, natal_planet, aspect) triple, the
      day when the orb is smallest. Only kept if the peak orb is < 1.5°.
    - sign ingresses: when a transit planet enters a new zodiac sign
      compared to the previous day.

    Returns a list of event dicts sorted by date (then by weight desc).
    If `top_n` is provided, keeps only the heaviest N overall.
    """
    hour = birth_dt.hour if birth_time_known else 12
    minute = birth_dt.minute if birth_time_known else 0

    natal_subject = AstrologicalSubjectFactory.from_birth_data(
        name="_natal",
        year=birth_dt.year, month=birth_dt.month, day=birth_dt.day,
        hour=hour, minute=minute,
        lat=lat, lng=lng, tz_str=tz_str,
        online=False,
    )

    triple_peaks: dict[tuple[str, str, str], dict[str, Any]] = {}
    ingresses: list[dict[str, Any]] = []
    prev_sign: dict[str, str] = {}

    for day_offset in range(days):
        d = start_date + timedelta(days=day_offset)
        # Noon UTC — a stable mid-day sample that catches aspects which are
        # exact during the day even if they're not exact at midnight.
        transit_subject = AstrologicalSubjectFactory.from_birth_data(
            name="_t",
            year=d.year, month=d.month, day=d.day,
            hour=12, minute=0,
            lat=0.0, lng=0.0, tz_str="UTC",
            online=False,
        )

        synastry = SynastryAspects(natal_subject, transit_subject)
        for aspect in synastry.all_aspects:
            aspect_raw = (
                getattr(aspect, "aspect", None) or getattr(aspect, "aspect_name", "")
            )
            if callable(aspect_raw):
                aspect_raw = aspect_raw()
            aspect_name = str(aspect_raw).lower()
            if aspect_name not in _PERIOD_SCAN_ORB:
                continue
            orb = abs(aspect.orbit)
            if orb > _PERIOD_SCAN_ORB[aspect_name]:
                continue

            tp = aspect.p2_name.lower()
            np = aspect.p1_name.lower()
            triple = (tp, np, aspect_name)
            cur = triple_peaks.get(triple)
            if cur is not None and cur["orb"] <= orb:
                continue
            weight = (
                PLANET_WEIGHT.get(tp, 1) + ASPECT_WEIGHT.get(aspect_name, 1)
            )
            triple_peaks[triple] = {
                "kind": "aspect",
                "date": d,
                "transit_planet": aspect.p2_name,
                "natal_planet": aspect.p1_name,
                "aspect": aspect_name,
                "orb": round(orb, 2),
                "weight": weight,
            }

        # Sign ingresses for the 10 classical planets only.
        for planet_attr in _PLANET_ATTRS:
            if not include_moon_ingresses and planet_attr in _FAST_MOON_PLANETS:
                # still update prev_sign so we don't emit a false ingress
                # on day-after-skipped flip.
                obj = getattr(transit_subject, planet_attr, None)
                if obj is not None:
                    prev_sign[planet_attr] = obj.sign
                continue
            obj = getattr(transit_subject, planet_attr, None)
            if obj is None:
                continue
            cur_sign = obj.sign
            prev = prev_sign.get(planet_attr)
            if prev and prev != cur_sign:
                ingresses.append({
                    "kind": "ingress",
                    "date": d,
                    "planet": planet_attr,
                    "from_sign": prev,
                    "to_sign": cur_sign,
                    "weight": PLANET_WEIGHT.get(planet_attr, 1),
                })
            prev_sign[planet_attr] = cur_sign

    events: list[dict[str, Any]] = []
    for info in triple_peaks.values():
        if info["orb"] <= _PERIOD_PEAK_ORB:
            events.append(info)
    events.extend(ingresses)

    if top_n:
        events = sorted(events, key=lambda e: -e.get("weight", 0))[:top_n]

    events.sort(key=lambda e: (e["date"], -e.get("weight", 0)))
    log.debug(
        "transits.period.scanned",
        days=days,
        events=len(events),
        peaks=len(triple_peaks),
        ingresses=len(ingresses),
    )
    return events
