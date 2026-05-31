"""HTML/CSS natal chart PDF renderer.

The public API mirrors ``services.natal_pdf.generate_natal_pdf`` but renders a
print-oriented HTML document through Playwright/Chromium. The old ReportLab
renderer remains the route fallback.
"""

from __future__ import annotations

import html
import math
from datetime import datetime
from typing import Any

from services.astro.planet_names import PLANET_GLYPH as PLANET_SYMBOLS
from services.astro.planet_names import PLANET_RU
from services.astro.sign_cases import sign_ru as _sign_case_ru
from services.natal_pdf import (
    ASPECT_ORDER,
    ASPECT_RU,
    ASPECT_SYMBOLS,
    ASPECT_TOPICS,
    ELEMENT_COPY,
    ELEMENTS,
    GLOSSARY,
    HOUSE_LABELS,
    HOUSE_TOPICS,
    PLANET_ORDER,
    SIGN_RU,
    SIGN_SYMBOLS,
)

GOLD = "#d6b85a"
GOLD_DIM = "#8d7842"
BG = "#050510"
PANEL = "#100c1f"
PANEL_DARK = "#0b0714"
WHEEL_BG = "#071029"
TEXT = "#f4f0e8"
TEXT_DIM = "#a9a1bb"
BORDER = "rgba(214, 184, 90, .22)"

ELEMENT_COLORS = {
    "fire": "#e05b30",
    "earth": "#1fa37c",
    "air": "#398ada",
    "water": "#5846b6",
}
ASPECT_COLORS = {
    "conjunction": GOLD,
    "trine": "#1fa37c",
    "sextile": "#96d957",
    "square": "#f0673c",
    "opposition": "#ff585f",
    "quincunx": "#8b65da",
}
PLANET_COLORS = {
    "sun": "#f3cf4e",
    "moon": "#cad4f3",
    "mercury": "#8dd05f",
    "venus": "#ef85a4",
    "mars": "#f05a5a",
    "jupiter": "#e8955c",
    "saturn": "#8f8f9a",
    "uranus": "#7b77e7",
    "neptune": "#78a9e8",
    "pluto": "#bb426b",
}
TOTAL_PAGES_TOKEN = "__TOTAL_PAGES__"


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _key(value: Any) -> str:
    return str(value or "").strip().lower()


def _sign_ru(sign: Any) -> str:
    return _sign_case_ru(sign)


def _sign_ru_case(sign: Any, case: str) -> str:
    if case == "prep":
        return _sign_case_ru(sign, "prep")
    if case == "gen":
        return _sign_case_ru(sign, "gen")
    return _sign_case_ru(sign)


def _sign_symbol(sign: Any) -> str:
    key = _key(sign)
    if key not in SIGN_SYMBOLS:
        reverse = {v.lower(): k for k, v in SIGN_RU.items()}
        key = reverse.get(key, key)
    return SIGN_SYMBOLS.get(key, "")


def _sign_abs_degree(sign: Any) -> float:
    sign_order = list(SIGN_RU.keys())
    key = _key(sign)
    return float(sign_order.index(key) * 30) if key in sign_order else 0.0


def _chart_abs_degree(point: dict[str, Any]) -> float:
    if point.get("degree") is not None:
        return float(point.get("degree") or 0) % 360
    return (_sign_abs_degree(point.get("sign")) + float(point.get("sign_degree") or 0)) % 360


def _planet_key(name: Any) -> str:
    raw = _key(name)
    reverse = {
        "солнце": "sun",
        "луна": "moon",
        "меркурий": "mercury",
        "венера": "venus",
        "марс": "mars",
        "юпитер": "jupiter",
        "сатурн": "saturn",
        "уран": "uranus",
        "нептун": "neptune",
        "плутон": "pluto",
    }
    return reverse.get(raw, raw)


def _aspect_key(name: Any) -> str:
    raw = _key(name)
    reverse = {
        "соединение": "conjunction",
        "трин": "trine",
        "секстиль": "sextile",
        "квадрат": "square",
        "оппозиция": "opposition",
        "квинконс": "quincunx",
    }
    return reverse.get(raw, raw)


def _roman(num: int) -> str:
    values = ((10, "X"), (9, "IX"), (8, "VIII"), (7, "VII"), (6, "VI"), (5, "V"), (4, "IV"), (1, "I"))
    out = ""
    rest = num
    for value, glyph in values:
        while rest >= value:
            out += glyph
            rest -= value
    return out


def _deg_str(deg: float | int | None, *, within_sign: bool = True) -> str:
    value = float(deg or 0)
    if within_sign:
        value = value % 30
    d = int(value)
    m = int((value - d) * 60)
    return f"{d}°{m:02d}'"


def _lines(text: str, max_words: int) -> str:
    words = str(text or "").replace("\n", " ").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(" .,;:") + "."


def _word_count(text: str) -> int:
    return len(str(text or "").split())


def _split_words(text: str, max_words: int) -> list[str]:
    words = str(text or "").split()
    if len(words) <= max_words:
        return [" ".join(words)] if words else []
    chunks = []
    for start in range(0, len(words), max_words):
        chunks.append(" ".join(words[start:start + max_words]))
    return chunks


def _description(entry: Any, fallback: str, *, words: int) -> str:
    if isinstance(entry, dict):
        source = str(entry.get("full") or entry.get("short") or "").strip()
    else:
        source = ""
    fallback = str(fallback or "").strip()
    if source and fallback and _word_count(source) < max(18, words // 2):
        source = f"{source} {fallback}"
    if not source:
        source = fallback
    return _lines(source, words)


def _planet_fallback(name: str, planet: dict[str, Any]) -> str:
    ru = PLANET_RU.get(name, name)
    sign = planet.get("sign_ru") or planet.get("sign")
    sign_prep = _sign_ru_case(sign, "prep")
    sign_gen = _sign_ru_case(sign, "gen")
    house = planet.get("house") or "?"
    retro = " Если планета ретроградна, её тема чаще проживается внутренне: через пересмотр привычек, задержки, возвращение к старым сюжетам и более внимательное отношение к собственным реакциям." if planet.get("retrograde") else ""
    return (
        f"{ru} в {sign_prep} показывает, каким стилем раскрывается эта часть личности; "
        f"в знаке {sign_gen} планета проявляется через реакции, выборы, инициативу и повторяющиеся ситуации. "
        f"{house}-й дом показывает сферу, где качество планеты заметнее всего: там чаще возникают "
        f"события, люди и задачи, через которые эта энергия становится практической. "
        f"В жизни это можно отслеживать по повторяющимся сценариям: где вы быстро включаетесь, "
        f"где сомневаетесь, а где чувствуете естественную силу и интерес.{retro}"
    )


def _house_fallback(house: dict[str, Any]) -> str:
    num = int(house.get("number") or 0)
    sign = house.get("sign_ru") or house.get("sign")
    sign_nom = _sign_ru(sign)
    sign_prep = _sign_ru_case(sign, "prep")
    topic = HOUSE_TOPICS.get(num, "важную сферу жизни")
    return (
        f"{num}-й дом описывает {topic}. Знак на куспиде — {sign_nom}; дом в {sign_prep} показывает, каким способом эта область "
        f"обычно раскрывается: спокойно или резко, через инициативу или ожидание, через контакт "
        f"с людьми или личную самостоятельность. Этот дом полезно читать как карту повседневных "
        f"сценариев: где вы чаще берёте ответственность, где ищете поддержку, где растёте через "
        f"опыт и где важно не повторять старые автоматические реакции."
    )


def _aspect_fallback(aspect: dict[str, Any]) -> str:
    p1 = PLANET_RU.get(_planet_key(aspect.get("p1")), str(aspect.get("p1") or "Планета"))
    p2 = PLANET_RU.get(_planet_key(aspect.get("p2")), str(aspect.get("p2") or "Планета"))
    topic = ASPECT_TOPICS.get(_aspect_key(aspect.get("aspect")), "создают важную внутреннюю связь")
    return (
        f"{p1} и {p2} {topic}. Этот аспект показывает, как две разные части характера "
        f"взаимодействуют между собой: где они помогают друг другу, а где создают напряжение "
        f"или внутренний спор. В повседневности он может проявляться через повторяющийся выбор, "
        f"тип реакции, стиль общения и способ принимать решения. Чем точнее орб, тем заметнее "
        f"эта тема в характере, отношениях и личных разворотах."
    )


def _aspect_description_map(descriptions: dict[str, Any] | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in ((descriptions or {}).get("aspects") or []):
        if not isinstance(entry, dict):
            continue
        p1 = _planet_key(entry.get("p1"))
        p2 = _planet_key(entry.get("p2"))
        atype = _aspect_key(entry.get("type") or entry.get("aspect"))
        if p1 and p2 and atype:
            out[(p1, p2, atype)] = entry
            out[(p2, p1, atype)] = entry
    return out


def _sign_element(sign: Any) -> str:
    sign_key = _key(sign)
    if sign_key not in SIGN_SYMBOLS:
        reverse = {v.lower(): k for k, v in SIGN_RU.items()}
        sign_key = reverse.get(sign_key, sign_key)
    for element, (_, signs) in ELEMENTS.items():
        if sign_key in signs:
            return element
    return "fire"


def _element_percentages(planets: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {element: 0 for element in ELEMENTS}
    for planet in planets.values():
        counts[_sign_element(planet.get("sign"))] += 1
    total = max(sum(counts.values()), 1)
    return {key: round(value / total * 100) for key, value in counts.items()}


def _dominant_element(planets: dict[str, dict[str, Any]]) -> str:
    percentages = _element_percentages(planets)
    return max(percentages.items(), key=lambda item: item[1])[0] if percentages else "fire"


def _format_birth_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def _section_header(title: str, subtitle: str, aside: str = "") -> str:
    aside_html = f'<div class="section-aside">{_e(aside)}</div>' if aside else ""
    return (
        f'<div class="section-head"><div><h2>{_e(title)}</h2>'
        f'<div class="rule"></div><p>{_e(subtitle)}</p></div>{aside_html}</div>'
    )


def _footer(page: int, total: int | str = TOTAL_PAGES_TOKEN) -> str:
    return f'<footer>ASTRO TMA · НАТАЛЬНАЯ КАРТА <span>{page} / {total}</span></footer>'


def _page(page: int, body: str, *, class_name: str = "") -> str:
    cls = f"page {class_name}".strip()
    return f'<section class="{cls}">{body}{_footer(page)}</section>'


def _card(title: str, body: str, *, class_name: str = "", meta: str = "", icon: str = "") -> str:
    icon_html = f'<div class="card-icon">{icon}</div>' if icon else ""
    meta_html = f'<div class="card-meta">{_e(meta)}</div>' if meta else ""
    return (
        f'<article class="card {class_name}">{icon_html}<h3>{title}</h3>'
        f'{meta_html}<div class="mini-rule"></div><p>{body}</p></article>'
    )


def _polar(cx: float, cy: float, radius: float, degree: float) -> tuple[float, float]:
    angle = math.radians(degree)
    return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius


def _ascendant_degree(houses: list[dict[str, Any]], asc_sign: str | None) -> float:
    for house in houses:
        if int(house.get("number") or 0) == 1:
            return _chart_abs_degree(house)
    return _sign_abs_degree(asc_sign)


def _wheel_angle(abs_degree: float, ascendant_degree: float) -> float:
    return 180 + (abs_degree - ascendant_degree)


def _natal_wheel_svg(
    planets: dict[str, dict[str, Any]],
    houses: list[dict[str, Any]],
    aspects: list[dict[str, Any]],
    asc_sign: str | None,
) -> str:
    cx = cy = 360
    outer = 315
    middle = 250
    inner = 170
    asc = _ascendant_degree(houses, asc_sign)
    sign_keys = list(SIGN_RU.keys())
    parts = [
        '<svg class="wheel-svg" viewBox="0 0 720 720" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="720" height="720" fill="{WHEEL_BG}"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{outer}" fill="none" stroke="{GOLD_DIM}" stroke-width="1"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{middle}" fill="none" stroke="{GOLD_DIM}" stroke-width=".8" opacity=".75"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{inner}" fill="none" stroke="{GOLD_DIM}" stroke-width=".8" opacity=".55"/>',
    ]
    for i, sign in enumerate(sign_keys):
        start = _wheel_angle(i * 30, asc)
        x1, y1 = _polar(cx, cy, middle, start)
        x2, y2 = _polar(cx, cy, outer, start)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD_DIM}" stroke-width=".7" opacity=".7"/>')
        gx, gy = _polar(cx, cy, 286, _wheel_angle(i * 30 + 15, asc))
        parts.append(f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" dominant-baseline="middle" fill="{GOLD}" font-size="30">{SIGN_SYMBOLS[sign]}</text>')
    ordered_houses = sorted([h for h in houses if int(h.get("number") or 0)], key=lambda h: int(h.get("number") or 0))
    for index, house in enumerate(ordered_houses):
        num = int(house.get("number") or 0)
        angle = _wheel_angle(_chart_abs_degree(house), asc)
        x1, y1 = _polar(cx, cy, inner, angle)
        x2, y2 = _polar(cx, cy, middle, angle)
        width = 1.3 if num in (1, 4, 7, 10) else .55
        color = GOLD if num in (1, 4, 7, 10) else GOLD_DIM
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}" opacity=".75"/>')
        next_house = ordered_houses[(index + 1) % len(ordered_houses)] if ordered_houses else house
        span = (_chart_abs_degree(next_house) - _chart_abs_degree(house)) % 360
        tx, ty = _polar(cx, cy, 210, _wheel_angle((_chart_abs_degree(house) + span / 2) % 360, asc))
        parts.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="middle" fill="{GOLD_DIM}" font-size="17">{_roman(num)}</text>')
    planet_points: dict[str, tuple[float, float]] = {}
    for name in PLANET_ORDER:
        planet = planets.get(name)
        if not planet:
            continue
        angle = _wheel_angle(_chart_abs_degree(planet), asc)
        px, py = _polar(cx, cy, 143, angle)
        planet_points[name] = (px, py)
    for aspect in sorted(aspects, key=lambda a: float(a.get("orb") or 99))[:16]:
        p1 = _planet_key(aspect.get("p1"))
        p2 = _planet_key(aspect.get("p2"))
        atype = _aspect_key(aspect.get("aspect"))
        if p1 not in planet_points or p2 not in planet_points:
            continue
        x1, y1 = planet_points[p1]
        x2, y2 = planet_points[p2]
        dash = ' stroke-dasharray="5 5"' if atype in ("sextile", "opposition", "quincunx") else ""
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{ASPECT_COLORS.get(atype, GOLD_DIM)}" stroke-width=".8" opacity=".55"{dash}/>')
    for name, (px, py) in planet_points.items():
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="15" fill="{BG}" stroke="{GOLD_DIM}" stroke-width="1"/>')
        parts.append(f'<text x="{px:.1f}" y="{py + 1:.1f}" text-anchor="middle" dominant-baseline="middle" fill="{PLANET_COLORS.get(name, GOLD)}" font-size="26">{PLANET_SYMBOLS.get(name, "")}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _donut_svg(percentages: dict[str, int], dominant: str) -> str:
    total = max(sum(percentages.values()), 1)
    radius = 80
    circumference = 2 * math.pi * radius
    offset = 0.0
    circles = []
    for element in ELEMENTS:
        pct = percentages.get(element, 0)
        length = circumference * pct / total
        circles.append(
            f'<circle class="donut-seg" r="{radius}" cx="110" cy="110" '
            f'stroke="{ELEMENT_COLORS[element]}" stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}"/>'
        )
        offset += length
    label = ELEMENTS[dominant][0]
    return (
        '<svg class="donut" viewBox="0 0 220 220">'
        '<circle r="80" cx="110" cy="110" fill="none" stroke="#141029" stroke-width="38"/>'
        f'{"".join(circles)}'
        f'<text x="110" y="103" text-anchor="middle" class="donut-kicker">ДОМИНАНТА</text>'
        f'<text x="110" y="129" text-anchor="middle" class="donut-label">{_e(label)} {percentages.get(dominant, 0)}%</text>'
        '</svg>'
    )


def _css() -> str:
    return f"""
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; overflow-wrap: anywhere; }}
html, body {{ margin: 0; padding: 0; background: {BG}; color: {TEXT}; }}
body {{ font-family: "DejaVu Sans", Arial, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ position: relative; display: block; width: 210mm; height: 297mm; overflow: hidden; padding: 22mm 18mm 17mm; background: {BG}; break-after: page; page-break-after: always; break-inside: avoid; }}
.cover {{ display: flex; flex-direction: column; align-items: center; text-align: center; padding-top: 30mm; }}
.mark {{ color: {GOLD}; font-size: 32px; margin-bottom: 34mm; line-height: 1; }}
h1, h2, h3, .serif {{ font-family: "DejaVu Serif", Georgia, serif; font-weight: 400; }}
h1 {{ margin: 0; color: {GOLD}; font-size: 34px; letter-spacing: 7px; text-transform: uppercase; }}
.cover-subtitle {{ margin-top: 12mm; font: italic 16px "DejaVu Serif", Georgia, serif; color: {TEXT}; opacity: .92; }}
.cover-name {{ margin-top: 36mm; font: italic 21px "DejaVu Serif", Georgia, serif; }}
.cover-meta {{ margin-top: 10mm; color: {TEXT_DIM}; font-size: 13px; line-height: 1.72; }}
.cover-points {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 19mm; margin-top: 6mm; width: 128mm; }}
.cover-point .glyph {{ color: {GOLD}; font-size: 28px; line-height: 1; }}
.cover-point .label {{ margin-top: 7mm; color: {TEXT_DIM}; font-size: 10.5px; letter-spacing: 3px; text-transform: uppercase; }}
.cover-point .value {{ margin-top: 6mm; font: 15px "DejaVu Serif", Georgia, serif; }}
.cover-line {{ width: 32mm; height: 1px; background: {GOLD_DIM}; margin-top: 20mm; }}
.cover-foot {{ margin-top: 8mm; color: #776f8c; font-size: 10px; letter-spacing: 3px; }}
.section-head {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8mm; }}
h2 {{ margin: 0; color: {GOLD}; font-size: 24px; letter-spacing: 4px; }}
.rule {{ height: 1px; width: 170mm; background: rgba(214,184,90,.2); margin: 6mm 0 5mm; }}
.section-head p {{ margin: 0; color: {TEXT_DIM}; font: italic 12px "DejaVu Serif", Georgia, serif; }}
.section-aside {{ color: #807894; font-size: 12px; margin-top: 5mm; }}
footer {{ position: absolute; bottom: 7mm; left: 0; right: 0; text-align: center; color: #6d6680; font-size: 10px; letter-spacing: 3px; }}
footer span {{ letter-spacing: 1px; margin-left: 8px; }}
.toc-list {{ margin-top: 22mm; }}
.toc-row {{ display: grid; grid-template-columns: 12mm 1fr 14mm; align-items: center; min-height: 16mm; border-bottom: 1px solid rgba(255,255,255,.025); }}
.toc-roman {{ color: {GOLD}; font: 15px "DejaVu Serif", Georgia, serif; }}
.toc-title {{ font: 14px "DejaVu Serif", Georgia, serif; }}
.toc-page {{ color: {TEXT_DIM}; text-align: right; font-size: 13px; }}
.cards-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6mm; }}
.grid-2 {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 4.5mm; }}
.card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7mm 6mm; min-height: 39mm; }}
.card h3 {{ margin: 0; color: {TEXT}; font-size: 15px; line-height: 1.25; }}
.card p {{ margin: 4mm 0 0; font-size: 11.4px; line-height: 1.43; color: {TEXT}; }}
.card-icon {{ color: {GOLD}; font-size: 25px; margin-bottom: 4mm; }}
.card-meta {{ color: {TEXT_DIM}; font-size: 10px; letter-spacing: .8px; text-transform: uppercase; margin-top: 1.5mm; }}
.mini-rule {{ width: 14mm; height: 1px; margin-top: 4mm; background: {GOLD_DIM}; }}
.key-card {{ text-align: center; min-height: 86mm; padding: 8mm 6mm 7mm; }}
.key-card .zodiac-dot {{ margin: 5mm auto 3mm; width: 7mm; height: 7mm; border-radius: 50%; display: grid; place-items: center; color: white; font-size: 15px; }}
.key-card .quote {{ margin-top: 5mm; color: {TEXT_DIM}; font: italic 11px "DejaVu Serif", Georgia, serif; }}
.key-card p {{ text-align: left; }}
.dominant-card {{ margin-top: 8mm; border-left: 3px solid {GOLD}; min-height: 35mm; display: grid; grid-template-columns: 12mm 1fr; gap: 5mm; align-items: center; }}
.dominant-symbol {{ font-size: 27px; color: var(--element-color); }}
.dominant-card h3 {{ color: {GOLD}; font-size: 17px; }}
.wheel-wrap {{ width: 164mm; height: 164mm; margin: 9mm auto 7mm; background: {WHEEL_BG}; }}
.wheel-svg {{ width: 100%; height: 100%; display: block; }}
.legend {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 3mm 24mm; width: 154mm; margin: 0 auto; color: {TEXT_DIM}; font-size: 11.5px; }}
.legend-line {{ display: inline-block; width: 13mm; height: 1px; margin-right: 4mm; vertical-align: middle; background: currentColor; }}
.elements-layout {{ display: grid; grid-template-columns: 78mm 1fr; gap: 9mm; align-items: center; margin-top: 10mm; }}
.donut {{ width: 72mm; height: 72mm; transform: rotate(-90deg); }}
.donut text {{ transform: rotate(90deg); transform-origin: 110px 110px; font-family: "DejaVu Serif", Georgia, serif; }}
.donut-seg {{ fill: none; stroke-width: 38; transform: rotate(-90deg); transform-origin: 110px 110px; }}
.donut-kicker {{ fill: #73b568; font-size: 11px; letter-spacing: 2px; }}
.donut-label {{ fill: {GOLD}; font-size: 17px; }}
.element-list {{ display: grid; gap: 3mm; }}
.element-row {{ display: grid; grid-template-columns: 9mm 1fr 12mm; align-items: center; background: {PANEL}; border: 1px solid {BORDER}; border-radius: 7px; padding: 3.5mm 4mm; font: 14px "DejaVu Serif", Georgia, serif; }}
.swatch {{ width: 6mm; height: 6mm; border-radius: 2px; background: var(--element-color); }}
.percent {{ color: {GOLD}; text-align: right; font-family: "DejaVu Sans"; font-weight: 700; }}
.element-cards {{ margin-top: 12mm; }}
.element-card h3 {{ color: var(--element-color); }}
.tags {{ margin-top: 8mm; display: flex; gap: 3mm; flex-wrap: wrap; }}
.tag {{ border: 1px solid rgba(224,91,48,.35); color: #d99072; background: rgba(224,91,48,.13); border-radius: 999px; padding: 1.5mm 5mm; font-size: 11px; }}
.planet-card {{ min-height: 79mm; }}
.planet-card .card-icon {{ font-size: 27px; color: var(--planet-color); }}
.retro {{ display: inline-block; margin-left: 3mm; padding: 1mm 3mm; border: 1px solid {GOLD_DIM}; border-radius: 999px; color: {GOLD}; font-size: 11px; letter-spacing: 1px; }}
.houses-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 3.4mm 4.5mm; }}
.house-card {{ min-height: 59mm; padding: 5mm; }}
.house-card.angle {{ border-left: 3px solid {GOLD}; background: {PANEL_DARK}; }}
.house-top {{ display: flex; justify-content: space-between; align-items: baseline; gap: 4mm; }}
.house-num {{ color: {GOLD}; font: 15.5px "DejaVu Serif", Georgia, serif; margin-right: 2mm; }}
.house-sign {{ font: 12px "DejaVu Serif", Georgia, serif; }}
.house-degree {{ color: {TEXT_DIM}; font-size: 11px; }}
.house-label {{ margin-top: 2mm; color: {TEXT_DIM}; font-size: 10.5px; letter-spacing: 1.4px; text-transform: uppercase; }}
.house-card p {{ margin-top: 3mm; font-size: 11px; line-height: 1.34; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 4mm; margin: 8mm 0 7mm; }}
.metric {{ text-align: center; background: {PANEL}; border: 1px solid {BORDER}; border-radius: 7px; padding: 4mm 0 3.5mm; }}
.metric strong {{ color: var(--metric-color, {GOLD}); display: block; font: 22px "DejaVu Serif", Georgia, serif; }}
.metric span {{ color: {TEXT_DIM}; font-size: 11px; letter-spacing: 1.2px; text-transform: uppercase; }}
.aspect-group {{ border-left: 3px solid var(--aspect-color); padding-left: 5mm; margin-top: 5.5mm; break-inside: avoid; }}
.aspect-group h3 {{ color: var(--aspect-color); font-size: 16.5px; letter-spacing: 1.2px; text-transform: uppercase; margin: 0 0 4mm; }}
.aspect-group h3 em {{ color: {TEXT_DIM}; text-transform: none; font-size: 12.5px; letter-spacing: 0; margin-left: 3mm; }}
.aspect-row {{ margin-bottom: 4mm; padding: 4mm 4.5mm; background: {PANEL}; border: 1px solid {BORDER}; border-radius: 7px; break-inside: avoid; }}
.aspect-title {{ display: grid; grid-template-columns: 1fr auto; align-items: start; gap: 5mm; color: {TEXT}; font-size: 13.5px; line-height: 1.2; }}
.aspect-title span:first-child {{ min-width: 0; }}
.orb {{ color: {TEXT_DIM}; white-space: nowrap; font-size: 11.5px; }}
.aspect-row p {{ margin: 2.5mm 0 0; color: {TEXT_DIM}; line-height: 1.32; font-size: 12.2px; }}
.reading {{ padding-right: 4mm; }}
.reading-quote {{ text-align: center; color: {TEXT_DIM}; font: italic 13px "DejaVu Serif", Georgia, serif; margin: 8mm 0 9mm; }}
.reading h3 {{ color: {GOLD}; font-size: 17px; letter-spacing: 1.5px; margin: 0 0 3mm; }}
.reading p {{ font-size: 13px; line-height: 1.48; margin: 0 0 7mm; }}
.final {{ display: flex; flex-direction: column; align-items: center; text-align: center; padding-top: 76mm; }}
.final .mark {{ margin-bottom: 20mm; }}
.final-copy {{ font: italic 16px/1.65 "DejaVu Serif", Georgia, serif; width: 92mm; }}
.glossary {{ margin-top: 24mm; width: 130mm; text-align: left; display: grid; grid-template-columns: repeat(2, 1fr); gap: 6mm 18mm; }}
.glossary-title {{ color: {GOLD}; font: 15px "DejaVu Serif", Georgia, serif; letter-spacing: 2px; margin-top: 20mm; }}
.glossary dt {{ color: {GOLD}; font: 12px "DejaVu Serif", Georgia, serif; margin-bottom: 2mm; }}
.glossary dd {{ margin: 0; color: {TEXT_DIM}; font-size: 11px; line-height: 1.28; }}
"""


def _content_page(*, planets_page: int, houses_page: int, aspects_page: int, reading_page: int) -> str:
    rows = [
        ("I", "Ключевые точки карты", "3"),
        ("II", "Натальное колесо", "4"),
        ("III", "Баланс стихий и характер", "5"),
        ("IV", "Планеты в знаках", str(planets_page)),
        ("V", "Дома гороскопа", str(houses_page)),
        ("VI", "Аспекты — связи между планетами", str(aspects_page)),
        ("VII", "Персональная интерпретация", str(reading_page)),
    ]
    body = _section_header("Содержание", "Что внутри отчёта")
    body += '<div class="toc-list">' + "".join(
        f'<div class="toc-row"><div class="toc-roman">{roman}</div><div class="toc-title">{_e(title)}</div><div class="toc-page">{page}</div></div>'
        for roman, title, page in rows
    ) + "</div>"
    return _page(2, body)


def _cover_page(user_name: str, birth_date: str, birth_time: str | None, birth_city: str, sun_sign: str, moon_sign: str, asc_sign: str | None) -> str:
    birth_bits = " · ".join(bit for bit in (_format_birth_date(birth_date), birth_time) if bit)
    points = [
        ("☉", "СОЛНЦЕ", _sign_ru(sun_sign)),
        ("☽", "ЛУНА", _sign_ru(moon_sign)),
        ("↑", "ВОСХОД", _sign_ru(asc_sign)),
    ]
    return _page(
        1,
        '<div class="mark">✦</div><h1>Натальная карта</h1>'
        '<div class="cover-subtitle">Персональный астрологический отчёт</div>'
        f'<div class="cover-name">{_e(user_name)}</div>'
        f'<div class="cover-meta">{_e(birth_bits)}<br>{_e(birth_city)}</div>'
        '<div class="cover-points">'
        + "".join(
            f'<div class="cover-point"><div class="glyph">{glyph}</div><div class="label">{label}</div><div class="value">{_e(value)}</div></div>'
            for glyph, label, value in points
        )
        + '</div><div class="cover-line"></div>'
        f'<div class="cover-foot">ASTRO TMA · MADE FOR {_e(user_name).upper()}</div>',
        class_name="cover",
    )


def _key_points_page(
    planets: dict[str, dict[str, Any]],
    sun_sign: str,
    moon_sign: str,
    asc_sign: str | None,
    descriptions: dict[str, Any] | None,
) -> str:
    planet_desc = (descriptions or {}).get("planets") or {}
    dominant = _dominant_element(planets)
    dominant_label = ELEMENTS[dominant][0]
    dominant_pct = _element_percentages(planets).get(dominant, 0)
    data = [
        ("sun", "☉", "СОЛНЦЕ", sun_sign, "«Как я сияю»", _description(planet_desc.get("sun"), _planet_fallback("sun", planets.get("sun", {"sign": sun_sign})), words=14)),
        ("moon", "☽", "ЛУНА", moon_sign, "«Что я чувствую»", _description(planet_desc.get("moon"), _planet_fallback("moon", planets.get("moon", {"sign": moon_sign})), words=14)),
        ("asc", "↑", "ВОСХОД", asc_sign, "«Как меня видят»", f"Восходящий знак {_sign_ru(asc_sign)} показывает первое впечатление, стиль реакции и внешний ритм."),
    ]
    body = _section_header("Ключевые точки", "Три центра, через которые читается ваша карта")
    body += '<div class="cards-3">' + "".join(
        f'<article class="card key-card"><div class="card-icon">{glyph}</div><div class="card-meta">{label}</div>'
        f'<div class="zodiac-dot" style="background:{ELEMENT_COLORS[_sign_element(sign)]}">{_sign_symbol(sign)}</div>'
        f'<h3>{_e(_sign_ru(sign))}</h3><div class="mini-rule"></div><div class="quote">{quote}</div><p>{_e(text)}</p></article>'
        for _key_name, glyph, label, sign, quote, text in data
    ) + "</div>"
    body += (
        f'<article class="card dominant-card" style="--element-color:{ELEMENT_COLORS[dominant]}">'
        f'<div class="dominant-symbol">△</div><div><h3>Доминирует {dominant_label.lower()}</h3>'
        f'<div class="card-meta">{dominant_pct}% карты</div><p>{_e(ELEMENT_COPY[dominant][0])}</p></div></article>'
    )
    return _page(3, body)


def _wheel_page(planets: dict[str, dict[str, Any]], houses: list[dict[str, Any]], aspects: list[dict[str, Any]], asc_sign: str | None) -> str:
    legend = [
        ("conjunction", "Соединение · слияние"),
        ("trine", "Трин · поток"),
        ("sextile", "Секстиль · возможность"),
        ("square", "Квадрат · вызов"),
        ("opposition", "Оппозиция · противостояние"),
        ("quincunx", "Квинконс · пересборка"),
    ]
    body = _section_header("Натальное колесо", "Карта неба в момент вашего рождения")
    body += f'<div class="wheel-wrap">{_natal_wheel_svg(planets, houses, aspects, asc_sign)}</div>'
    body += '<div class="legend">' + "".join(
        f'<div style="color:{ASPECT_COLORS[k]}"><span class="legend-line"></span>{_e(label)}</div>' for k, label in legend
    ) + "</div>"
    return _page(4, body)


def _elements_page(planets: dict[str, dict[str, Any]]) -> str:
    percentages = _element_percentages(planets)
    dominant = _dominant_element(planets)
    body = _section_header("Баланс стихий", "Как распределена энергия вашей карты")
    body += '<div class="elements-layout">'
    body += _donut_svg(percentages, dominant)
    body += '<div class="element-list">' + "".join(
        f'<div class="element-row" style="--element-color:{ELEMENT_COLORS[element]}"><span class="swatch"></span>'
        f'<span>{_e(ELEMENTS[element][0])}</span><span class="percent">{percentages.get(element, 0)}%</span></div>'
        for element in ELEMENTS
    ) + "</div></div>"
    body += '<div class="grid-2 element-cards">' + "".join(
        f'<article class="card element-card" style="--element-color:{ELEMENT_COLORS[element]}"><h3>{_e(ELEMENTS[element][0])}'
        f'<span class="percent" style="float:right">{percentages.get(element, 0)}%</span></h3><p>{_e(ELEMENT_COPY[element][0])}</p></article>'
        for element in ELEMENTS
    ) + "</div>"
    body += '<div class="tags">' + "".join(f'<span class="tag">{_e(tag)}</span>' for tag in ELEMENT_COPY[dominant][1]) + "</div>"
    return _page(5, body)


def _planet_pages(planets: dict[str, dict[str, Any]], descriptions: dict[str, Any] | None, *, start_page: int) -> list[str]:
    planet_desc = (descriptions or {}).get("planets") or {}
    items = [name for name in PLANET_ORDER if planets.get(name)]
    chunks = [items[index:index + 4] for index in range(0, len(items), 4)]
    pages = []
    for idx, chunk in enumerate(chunks, start=1):
        body = _section_header("Планеты в знаках", "Где находится каждая планета и что это значит", f"{idx} / {len(chunks)}")
        body += '<div class="grid-2">'
        for name in chunk:
            planet = planets[name]
            sign = planet.get("sign_ru") or planet.get("sign")
            retro = '<span class="retro">℞ РЕТРО</span>' if planet.get("retrograde") else ""
            meta = f'{_roman(int(planet.get("house") or 0))} дом · {_deg_str(planet.get("sign_degree", planet.get("degree", 0)))}'
            body += _card(
                f'{PLANET_RU[name]} в {_sign_ru(sign)} {retro}',
                _e(_description(planet_desc.get(name), _planet_fallback(name, planet), words=95)),
                class_name="planet-card",
                meta=meta,
                icon=f'<span style="color:{PLANET_COLORS.get(name, GOLD)}">{PLANET_SYMBOLS.get(name, "")}</span>',
            )
        body += "</div>"
        pages.append(_page(start_page + idx - 1, body))
    return pages


def _houses_pages(houses: list[dict[str, Any]], descriptions: dict[str, Any] | None, *, start_page: int) -> list[str]:
    house_desc = (descriptions or {}).get("houses") or {}
    axis = {1: "Асцендент", 4: "Основание (IC)", 7: "Десцендент", 10: "Середина неба (MC)"}
    items = [house for house in houses if int(house.get("number") or 0)]
    chunks = [items[index:index + 6] for index in range(0, len(items), 6)]
    pages = []
    for idx, chunk in enumerate(chunks, start=1):
        body = _section_header("Дома гороскопа", "12 сфер жизни и их обстановка", f"{idx} / {len(chunks)}")
        body += '<div class="houses-grid">'
        for house in chunk:
            num = int(house.get("number") or 0)
            sign = house.get("sign_ru") or house.get("sign")
            angle_cls = " angle" if num in axis else ""
            axis_html = f'<div class="card-meta" style="color:{GOLD}">{axis[num]}</div>' if num in axis else ""
            body += (
                f'<article class="card house-card{angle_cls}"><div class="house-top"><div>'
                f'<span class="house-num">{_roman(num)}</span><span class="house-sign">{_sign_symbol(sign)} {_e(_sign_ru(sign))}</span></div>'
                f'<div class="house-degree">{_deg_str(house.get("degree"), within_sign=False)}</div></div>{axis_html}'
                f'<div class="house-label">{_e(HOUSE_LABELS.get(num, f"ДОМ {num}"))}</div>'
                f'<p>{_e(_description(house_desc.get(str(num)), _house_fallback(house), words=68))}</p></article>'
            )
        body += "</div>"
        pages.append(_page(start_page + idx - 1, body))
    return pages


def _aspect_pages(aspects: list[dict[str, Any]], descriptions: dict[str, Any] | None, *, start_page: int) -> list[str]:
    aspect_desc = _aspect_description_map(descriptions)
    groups = [(atype, [a for a in aspects if _aspect_key(a.get("aspect")) == atype]) for atype in ASPECT_ORDER]
    groups = [(atype, group) for atype, group in groups if group]
    total = sum(len(group) for _, group in groups)
    harm = sum(1 for a in aspects if _aspect_key(a.get("aspect")) in ("trine", "sextile"))
    chall = sum(1 for a in aspects if _aspect_key(a.get("aspect")) in ("square", "opposition"))
    neutral = max(total - harm - chall, 0)
    metric_html = (
        '<div class="metrics">'
        f'<div class="metric"><strong>{total}</strong><span>Всего</span></div>'
        f'<div class="metric" style="--metric-color:#1fa37c"><strong>{harm}</strong><span>Гармоничных</span></div>'
        f'<div class="metric" style="--metric-color:#f0673c"><strong>{chall}</strong><span>Напряжённых</span></div>'
        f'<div class="metric" style="--metric-color:{TEXT_DIM}"><strong>{neutral}</strong><span>Нейтральных</span></div>'
        '</div>'
    )
    chunks: list[list[tuple[str, list[dict[str, Any]]]]] = []
    for atype, group_items in groups:
        for index in range(0, len(group_items), 3):
            group_chunk = group_items[index:index + 3]
            chunks.append([(atype, group_chunk)])
    pages = []
    for idx, chunk in enumerate(chunks, start=1):
        page_index = start_page + idx - 1
        body = _section_header("Аспекты", "Связи между планетами вашей карты")
        if idx == 1:
            body += metric_html
        for atype, group_items in chunk:
            color = ASPECT_COLORS.get(atype, GOLD)
            body += f'<section class="aspect-group" style="--aspect-color:{color}"><h3>{ASPECT_SYMBOLS.get(atype, "")} {ASPECT_RU.get(atype, atype)} <em>— {_e(ASPECT_TOPICS.get(atype, ""))}</em></h3>'
            for aspect in group_items:
                p1 = _planet_key(aspect.get("p1"))
                p2 = _planet_key(aspect.get("p2"))
                desc = _description(aspect_desc.get((p1, p2, atype)), _aspect_fallback(aspect), words=82)
                body += (
                    f'<div class="aspect-row"><div class="aspect-title"><span>{PLANET_SYMBOLS.get(p1, "")} {_e(PLANET_RU.get(p1, p1))} '
                    f'{ASPECT_SYMBOLS.get(atype, "")} {PLANET_SYMBOLS.get(p2, "")} {_e(PLANET_RU.get(p2, p2))}</span>'
                    f'<span class="orb">орб {float(aspect.get("orb") or 0):.1f}°</span></div><p>{_e(desc)}</p></div>'
                )
            body += "</section>"
        pages.append(_page(page_index, body))
    return pages


def _reading_pages(reading: str | None, sun_sign: str, moon_sign: str, asc_sign: str | None) -> list[str]:
    text = str(reading or "").strip()
    if not text:
        text = (
            f"**Ядро личности**\nВаша карта соединяет Солнце в {_sign_ru(sun_sign)}, Луну в {_sign_ru(moon_sign)}"
            f"{' и восходящий знак ' + _sign_ru(asc_sign) if asc_sign else ''}. Это сочетание показывает главный рисунок характера, эмоциональные потребности и то, как вас считывают другие.\n\n"
            "**Совет и путь**\nЧитайте отчёт как карту внимания: он не фиксирует судьбу, а помогает увидеть сильные стороны, зоны роста и темы, с которыми стоит обращаться осознанно."
        )
    blocks: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("**") and line.endswith("**"):
            if current_title or current_lines:
                blocks.append((current_title, " ".join(current_lines)))
            current_title = line.strip("* ")
            current_lines = []
        else:
            current_lines.append(line)
    if current_title or current_lines:
        blocks.append((current_title or "Персональная интерпретация", " ".join(current_lines)))
    expanded_blocks: list[tuple[str, str]] = []
    for title, paragraph in blocks:
        chunks = _split_words(paragraph, 260)
        if not chunks:
            continue
        expanded_blocks.append((title, chunks[0]))
        expanded_blocks.extend((f"{title} · продолжение", chunk) for chunk in chunks[1:])

    page_chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_words = 0
    limits = [150, 190]
    for title, paragraph in expanded_blocks:
        block_words = _word_count(paragraph) + 10
        limit = limits[min(len(page_chunks), len(limits) - 1)]
        if current and current_words + block_words > limit:
            page_chunks.append(current)
            current = []
            current_words = 0
        current.append((title, paragraph))
        current_words += block_words
    if current:
        page_chunks.append(current)

    pages = []
    for idx, chunk in enumerate(page_chunks, start=11):
        if not chunk:
            continue
        body = _section_header("Персональная интерпретация", "Написано специально для вас")
        if idx == 11:
            body += '<div class="reading-quote">«Каждый рисунок звёзд раскрывается только через того, кто его носит»</div>'
        body += '<div class="reading">' + "".join(
            f'<h3>✦ {_e(title)}</h3><p>{_e(paragraph)}</p>' for title, paragraph in chunk
        ) + "</div>"
        pages.append(_page(idx, body))
    return pages


def _final_page(page: int) -> str:
    body = (
        '<div class="mark">✦</div><div class="final-copy">Этот отчёт создан для вашего понимания<br>личного космического рисунка.</div>'
        '<div class="cover-line"></div><div class="glossary-title">Краткий справочник</div><dl class="glossary">'
    )
    for term, definition in GLOSSARY:
        body += f'<div><dt>{_e(term)}</dt><dd>{_e(definition)}</dd></div>'
    body += '</dl><div class="cover-foot">ASTRO TMA · СОЗДАНО ДЛЯ ВАС</div>'
    return _page(page, body, class_name="final")


def build_natal_pdf_html(
    user_name: str,
    birth_date: str,
    birth_time: str | None,
    birth_city: str,
    sun_sign: str,
    moon_sign: str,
    asc_sign: str | None,
    planets: dict[str, dict[str, Any]],
    houses: list[dict[str, Any]],
    aspects: list[dict[str, Any]],
    reading: str | None = None,
    descriptions: dict[str, Any] | None = None,
) -> str:
    planet_pages = _planet_pages(planets, descriptions, start_page=6)
    houses_start = 6 + len(planet_pages)
    house_pages = _houses_pages(houses, descriptions, start_page=houses_start)
    aspects_start = houses_start + len(house_pages)
    aspect_pages = _aspect_pages(aspects, descriptions, start_page=aspects_start)
    reading_start = aspects_start + len(aspect_pages)
    pages = [
        _cover_page(user_name, birth_date, birth_time, birth_city, sun_sign, moon_sign, asc_sign),
        _content_page(
            planets_page=6,
            houses_page=houses_start,
            aspects_page=aspects_start,
            reading_page=reading_start,
        ),
        _key_points_page(planets, sun_sign, moon_sign, asc_sign, descriptions),
        _wheel_page(planets, houses, aspects, asc_sign),
        _elements_page(planets),
        *planet_pages,
        *house_pages,
        *aspect_pages,
        *_reading_pages(reading, sun_sign, moon_sign, asc_sign),
    ]
    pages.append(_final_page(len(pages) + 1))
    body = "".join(pages).replace(TOTAL_PAGES_TOKEN, str(len(pages)))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{_css()}</style></head><body>{body}</body></html>"


async def generate_natal_pdf_html(
    user_name: str,
    birth_date: str,
    birth_time: str | None,
    birth_city: str,
    sun_sign: str,
    moon_sign: str,
    asc_sign: str | None,
    planets: dict[str, dict[str, Any]],
    houses: list[dict[str, Any]],
    aspects: list[dict[str, Any]],
    reading: str | None = None,
    descriptions: dict[str, Any] | None = None,
) -> bytes:
    from playwright.async_api import async_playwright

    document = build_natal_pdf_html(
        user_name=user_name,
        birth_date=birth_date,
        birth_time=birth_time,
        birth_city=birth_city,
        sun_sign=sun_sign,
        moon_sign=moon_sign,
        asc_sign=asc_sign,
        planets=planets,
        houses=houses,
        aspects=aspects,
        reading=reading,
        descriptions=descriptions,
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=1)
            await page.set_content(document, wait_until="load")
            return await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
            )
        finally:
            await browser.close()
