"""HTML/CSS Destiny Matrix PDF renderer (V2).

Mirrors ``services.natal_pdf_html`` — builds a print-oriented HTML document
and renders it through Playwright/Chromium. No ReportLab fallback here;
the route catches exceptions and surfaces a 502 to the client.

V2 scope:
    * cover, contents, octagram (same as MVP)
    * 8 narrative sections, each now augmented with 3 arcana mini-cards
      (meaning + plus/minus from ``arcana_meanings``) and a hardcoded
      practice-template block (bulleted action steps)
    * mini-glossary page(s) — all 22 arcana × ~40 words
    * 36-slot summary table
    * disclaimer / final page
"""

from __future__ import annotations

import html
import math
from datetime import datetime
from typing import Any

from services.destiny_matrix.arcana_names import (
    ARCANA_KEYWORDS_RU,
    ARCANA_NAMES_RU,
)
from services.destiny_matrix.interpreter import SECTION_KEYS, SECTION_LABELS_RU

# ── Palette (matches DestinyOctagram + natal PDF) ──────────────────────────

GOLD = "#d6b85a"
GOLD_DIM = "#8d7842"
BG = "#050510"
PANEL = "#100c1f"
PANEL_DARK = "#0b0714"
WHEEL_BG = "#071029"
TEXT = "#f4f0e8"
TEXT_DIM = "#a9a1bb"
BORDER = "rgba(214, 184, 90, .22)"

# Octagram-specific colours (lifted from DestinyOctagram.tsx)
COLOR_DIAMOND = "#f4d76b"
COLOR_SQUARE = "#a7c0ff"
COLOR_FAMILY_M = "#5fa8ff"   # синяя стрелка (мужская линия)
COLOR_FAMILY_F = "#ff7a92"   # красная стрелка (женская линия)
COLOR_HEART = "#ff7a92"
COLOR_DOLLAR = "#f4d76b"

TOTAL_PAGES_TOKEN = "__TOTAL_PAGES__"


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _arcana_name(num: int | None) -> str:
    if num is None:
        return ""
    return ARCANA_NAMES_RU.get(int(num), f"Аркан {num}")


def _arcana_keywords(num: int | None) -> str:
    if num is None:
        return ""
    return ", ".join(ARCANA_KEYWORDS_RU.get(int(num), []))


def _format_birth_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def _footer(page: int, total: int | str = TOTAL_PAGES_TOKEN) -> str:
    return f'<footer>ASTRO TMA · МАТРИЦА СУДЬБЫ <span>{page} / {total}</span></footer>'


def _page(page: int, body: str, *, class_name: str = "") -> str:
    cls = f"page {class_name}".strip()
    return f'<section class="{cls}">{body}{_footer(page)}</section>'


def _section_header(title: str, subtitle: str, aside: str = "") -> str:
    aside_html = f'<div class="section-aside">{_e(aside)}</div>' if aside else ""
    return (
        f'<div class="section-head"><div><h2>{_e(title)}</h2>'
        f'<div class="rule"></div><p>{_e(subtitle)}</p></div>{aside_html}</div>'
    )


# ── CSS ─────────────────────────────────────────────────────────────────────


def _css() -> str:
    return f"""
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; overflow-wrap: anywhere; }}
html, body {{ margin: 0; padding: 0; background: {BG}; color: {TEXT}; }}
body {{ font-family: "DejaVu Sans", Arial, sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ position: relative; display: block; width: 210mm; height: 297mm; overflow: hidden; padding: 22mm 18mm 17mm; background: {BG}; break-after: page; page-break-after: always; break-inside: avoid; }}
h1, h2, h3, .serif {{ font-family: "DejaVu Serif", Georgia, serif; font-weight: 400; }}

/* Cover */
.cover {{ display: flex; flex-direction: column; align-items: center; text-align: center; padding-top: 30mm; }}
.mark {{ color: {GOLD}; font-size: 32px; margin-bottom: 30mm; line-height: 1; }}
h1 {{ margin: 0; color: {GOLD}; font-size: 32px; letter-spacing: 6px; text-transform: uppercase; }}
.cover-subtitle {{ margin-top: 12mm; font: italic 16px "DejaVu Serif", Georgia, serif; color: {TEXT}; opacity: .92; }}
.cover-name {{ margin-top: 30mm; font: italic 21px "DejaVu Serif", Georgia, serif; }}
.cover-meta {{ margin-top: 10mm; color: {TEXT_DIM}; font-size: 13px; line-height: 1.72; }}
.cover-points {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14mm; margin-top: 8mm; width: 150mm; }}
.cover-point .num {{ color: {GOLD}; font: 26px "DejaVu Serif", Georgia, serif; }}
.cover-point .label {{ margin-top: 6mm; color: {TEXT_DIM}; font-size: 10.5px; letter-spacing: 2.5px; text-transform: uppercase; }}
.cover-point .value {{ margin-top: 4mm; font: 13px "DejaVu Serif", Georgia, serif; }}
.cover-line {{ width: 32mm; height: 1px; background: {GOLD_DIM}; margin-top: 16mm; }}
.cover-foot {{ margin-top: 8mm; color: #776f8c; font-size: 10px; letter-spacing: 3px; }}

/* Section heads */
.section-head {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8mm; }}
h2 {{ margin: 0; color: {GOLD}; font-size: 24px; letter-spacing: 4px; }}
.rule {{ height: 1px; width: 170mm; background: rgba(214,184,90,.2); margin: 6mm 0 5mm; }}
.section-head p {{ margin: 0; color: {TEXT_DIM}; font: italic 12px "DejaVu Serif", Georgia, serif; }}
.section-aside {{ color: #807894; font-size: 12px; margin-top: 5mm; }}
footer {{ position: absolute; bottom: 7mm; left: 0; right: 0; text-align: center; color: #6d6680; font-size: 10px; letter-spacing: 3px; }}
footer span {{ letter-spacing: 1px; margin-left: 8px; }}

/* TOC */
.toc-list {{ margin-top: 20mm; }}
.toc-row {{ display: grid; grid-template-columns: 12mm 1fr 14mm; align-items: center; min-height: 14mm; border-bottom: 1px solid rgba(255,255,255,.025); }}
.toc-roman {{ color: {GOLD}; font: 14px "DejaVu Serif", Georgia, serif; }}
.toc-title {{ font: 13px "DejaVu Serif", Georgia, serif; }}
.toc-page {{ color: {TEXT_DIM}; text-align: right; font-size: 13px; }}

/* Octagram page */
.octa-wrap {{ width: 168mm; height: 168mm; margin: 6mm auto 6mm; background: {BG}; display: grid; place-items: center; }}
.octa-svg {{ width: 100%; height: 100%; display: block; }}
.octa-caption {{ text-align: center; color: {TEXT_DIM}; font: italic 12px "DejaVu Serif", Georgia, serif; margin-top: 2mm; }}
.octa-anchors {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 5mm; margin-top: 8mm; }}
.octa-anchor {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 7px; padding: 5mm; text-align: center; }}
.octa-anchor .num {{ color: {GOLD}; font: 23px "DejaVu Serif", Georgia, serif; }}
.octa-anchor .label {{ color: {TEXT_DIM}; font-size: 10px; letter-spacing: 2px; text-transform: uppercase; margin-top: 2mm; }}
.octa-anchor .name {{ font: 12.5px "DejaVu Serif", Georgia, serif; margin-top: 2mm; }}

/* Narrative pages */
.section-card {{ background: {PANEL}; border: 1px solid {BORDER}; border-left: 3px solid {GOLD}; border-radius: 8px; padding: 6mm 7mm; }}
.section-card .anchor {{ display: flex; gap: 6mm; align-items: center; margin-bottom: 5mm; padding-bottom: 4mm; border-bottom: 1px solid rgba(214,184,90,.18); }}
.section-card .anchor .num {{ color: {GOLD}; font: 30px "DejaVu Serif", Georgia, serif; line-height: 1; }}
.section-card .anchor .name {{ font: 16px "DejaVu Serif", Georgia, serif; }}
.section-card .anchor .keywords {{ color: {TEXT_DIM}; font-size: 11px; margin-top: 1.5mm; }}
.section-card p {{ font-size: 12.5px; line-height: 1.5; margin: 0 0 4mm; }}
.section-card p:last-child {{ margin-bottom: 0; }}
.section-quote {{ text-align: center; color: {TEXT_DIM}; font: italic 12.5px "DejaVu Serif", Georgia, serif; margin: 4mm 0 5mm; }}

/* V2: decoded arcana mini-cards inside each narrative section */
.arc-trio {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin-top: 5mm; }}
.arc-card {{ background: {PANEL_DARK}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4mm; min-height: 38mm; }}
.arc-card .head {{ display: flex; align-items: baseline; gap: 3mm; margin-bottom: 2mm; }}
.arc-card .num {{ color: {GOLD}; font: 18px "DejaVu Serif", Georgia, serif; line-height: 1; }}
.arc-card .name {{ font: 11.5px "DejaVu Serif", Georgia, serif; line-height: 1.2; }}
.arc-card .ctx {{ color: {TEXT_DIM}; font-size: 9px; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 2mm; }}
.arc-card .body {{ color: {TEXT}; font-size: 10px; line-height: 1.4; margin: 0 0 2.5mm; }}
.arc-card .pm {{ font-size: 9.5px; line-height: 1.35; margin: 0; }}
.arc-card .pm .pl {{ color: #8fd497; font-weight: 600; }}
.arc-card .pm .mn {{ color: #ff8b8b; font-weight: 600; }}
.arc-card .pro {{ color: {TEXT_DIM}; font-size: 9px; margin-top: 2mm; font-style: italic; }}

/* V2: practice template blocks */
.practice {{ background: rgba(20,16,28,.55); border: 1px solid {BORDER}; border-radius: 8px; padding: 5mm 6mm; margin-top: 5mm; }}
.practice h3 {{ color: {GOLD}; font: 13px "DejaVu Serif", Georgia, serif; letter-spacing: 1.5px; text-transform: uppercase; margin: 0 0 3mm; }}
.practice ul {{ margin: 0; padding-left: 5mm; }}
.practice li {{ font-size: 11px; line-height: 1.45; margin-bottom: 2mm; color: {TEXT}; }}
.practice li:last-child {{ margin-bottom: 0; }}
.practice .affirm {{ margin-top: 4mm; padding: 3mm; border-left: 2px solid {GOLD}; color: {TEXT}; font: italic 11.5px "DejaVu Serif", Georgia, serif; background: rgba(214,184,90,.05); }}

/* V2: glossary */
.glossary-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 3mm 5mm; margin-top: 6mm; }}
.gloss-cell {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; padding: 3.5mm 4mm; min-height: 22mm; }}
.gloss-cell .head {{ display: flex; align-items: baseline; gap: 3mm; }}
.gloss-cell .num {{ color: {GOLD}; font: 16px "DejaVu Serif", Georgia, serif; line-height: 1; }}
.gloss-cell .name {{ font: 12px "DejaVu Serif", Georgia, serif; }}
.gloss-cell .kw {{ color: {TEXT_DIM}; font-size: 9.5px; margin-top: 1mm; letter-spacing: .5px; }}
.gloss-cell p {{ margin: 2mm 0 0; font-size: 10px; line-height: 1.4; color: {TEXT}; }}

/* Summary table */
.summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm 4mm; margin-top: 6mm; }}
.summary-cell {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; padding: 3.5mm 4mm; min-height: 18mm; }}
.summary-cell .num {{ color: {GOLD}; font: 18px "DejaVu Serif", Georgia, serif; line-height: 1; }}
.summary-cell .label {{ color: {TEXT_DIM}; font-size: 9.5px; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 2mm; }}
.summary-cell .name {{ font-size: 11px; margin-top: 2mm; line-height: 1.25; }}
.summary-section {{ grid-column: 1 / -1; color: {GOLD}; font: 13px "DejaVu Serif", Georgia, serif; letter-spacing: 2px; text-transform: uppercase; margin: 4mm 0 0; }}

/* Final */
.final {{ display: flex; flex-direction: column; align-items: center; text-align: center; padding-top: 60mm; }}
.final .mark {{ margin-bottom: 18mm; }}
.final-copy {{ font: italic 15px/1.65 "DejaVu Serif", Georgia, serif; width: 130mm; color: {TEXT}; }}
.disclaimer {{ margin-top: 22mm; width: 140mm; color: {TEXT_DIM}; font-size: 11px; line-height: 1.5; text-align: left; }}
.disclaimer h3 {{ color: {GOLD}; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; margin: 0 0 4mm; text-align: center; }}
"""


# ── Octagram SVG ────────────────────────────────────────────────────────────


def _ray_corner_dot(corner_xy: tuple[float, float], center_xy: tuple[float, float], t: float) -> tuple[float, float]:
    cx, cy = corner_xy
    mx, my = center_xy
    return cx + (mx - cx) * t, cy + (my - cy) * t


def _octagram_svg(positions: dict[str, Any]) -> str:
    """Project the React DestinyOctagram into static SVG.

    Geometry mirrors ``frontend/src/components/destiny/DestinyOctagram.tsx``:
    viewBox 600x600, centre (300, 300), R = 220 for personality diamond
    corners, R = 220 / sqrt(2) for ancestral square corners.
    """
    pers = positions.get("personality", {})
    sq = positions.get("ancestral_square", {})
    specials = positions.get("specials", {}) or {}
    money_diag = positions.get("money_diagonal") or []

    cx = cy = 300.0
    r_diamond = 220.0
    r_square = r_diamond * 0.78

    # Diamond corners (personality)
    top = (cx, cy - r_diamond)
    right = (cx + r_diamond, cy)
    bottom = (cx, cy + r_diamond)
    left = (cx - r_diamond, cy)
    # Square corners (ancestral)
    tl = (cx - r_square, cy - r_square)
    tr = (cx + r_square, cy - r_square)
    br = (cx + r_square, cy + r_square)
    bl = (cx - r_square, cy + r_square)

    parts: list[str] = [
        '<svg class="octa-svg" viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg">',
        # Diamond + square outlines
        f'<polygon points="{top[0]},{top[1]} {right[0]},{right[1]} {bottom[0]},{bottom[1]} {left[0]},{left[1]}" '
        f'fill="none" stroke="{COLOR_DIAMOND}" stroke-width="1.6" opacity=".85"/>',
        f'<polygon points="{tl[0]},{tl[1]} {tr[0]},{tr[1]} {br[0]},{br[1]} {bl[0]},{bl[1]}" '
        f'fill="none" stroke="{COLOR_SQUARE}" stroke-width="1.6" opacity=".85"/>',
        # Diagonal rays (corner → centre, terminating at R_INNER = 155)
    ]
    r_inner = 155.0
    for corner in (top, right, bottom, left, tl, tr, br, bl):
        dx, dy = corner[0] - cx, corner[1] - cy
        dist = math.hypot(dx, dy)
        if not dist:
            continue
        ix = cx + dx / dist * r_inner
        iy = cy + dy / dist * r_inner
        parts.append(
            f'<line x1="{corner[0]:.1f}" y1="{corner[1]:.1f}" x2="{ix:.1f}" y2="{iy:.1f}" '
            f'stroke="{GOLD_DIM}" stroke-width=".8" opacity=".55"/>'
        )

    # Family-line arrows (faint, just to hint at TL↔BR and TR↔BL diagonals)
    parts.append(
        f'<line x1="{tl[0]}" y1="{tl[1]}" x2="{br[0]}" y2="{br[1]}" '
        f'stroke="{COLOR_FAMILY_M}" stroke-width="1" opacity=".35"/>'
    )
    parts.append(
        f'<line x1="{tr[0]}" y1="{tr[1]}" x2="{bl[0]}" y2="{bl[1]}" '
        f'stroke="{COLOR_FAMILY_F}" stroke-width="1" opacity=".35"/>'
    )

    # Money diagonal (dashed): centre → BR area
    if money_diag:
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{br[0]:.1f}" y2="{br[1]:.1f}" '
            f'stroke="{COLOR_DOLLAR}" stroke-width="1" stroke-dasharray="4 4" opacity=".55"/>'
        )

    # Big corner nodes
    R_DOT = 26.0
    nodes = [
        (top, pers.get("month"), "Месяц"),
        (right, pers.get("year"), "Год"),
        (bottom, pers.get("bottom"), "Низ"),
        (left, pers.get("day"), "День"),
        (tl, sq.get("top_left"), "Род ↖"),
        (tr, sq.get("top_right"), "Род ↗"),
        (br, sq.get("bottom_right"), "Род ↘"),
        (bl, sq.get("bottom_left"), "Род ↙"),
    ]
    for (x, y), num, _label in nodes:
        if num is None:
            continue
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{R_DOT}" fill="{BG}" '
            f'stroke="{GOLD}" stroke-width="1.4"/>'
        )
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" dy="0.35em" '
            f'fill="{GOLD}" font-size="22" font-family="DejaVu Serif, Georgia, serif">{int(num)}</text>'
        )

    # Centre
    center_val = pers.get("center")
    if center_val is not None:
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R_DOT + 4}" fill="{BG}" '
            f'stroke="{GOLD}" stroke-width="1.6"/>'
        )
        parts.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" dy="0.35em" '
            f'fill="{GOLD}" font-size="24" font-family="DejaVu Serif, Georgia, serif">{int(center_val)}</text>'
        )

    # Mid-of-ray dots (specials.talent / character / money / love)
    R_MID = 16.0
    mid_t = 0.42  # along corner → centre, from corner
    mid_dots = [
        (top, specials.get("talent")),
        (left, specials.get("character")),
        (right, specials.get("money")),
        (bottom, specials.get("love")),
    ]
    for corner, num in mid_dots:
        if num is None:
            continue
        x, y = _ray_corner_dot(corner, (cx, cy), mid_t)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{R_MID}" fill="{BG}" '
            f'stroke="{GOLD_DIM}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dy="0.35em" '
            f'fill="{GOLD}" font-size="14" font-family="DejaVu Serif, Georgia, serif">{int(num)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


# ── Pages ──────────────────────────────────────────────────────────────────


def _cover_page(user_name: str, birth_date: str, positions: dict[str, Any]) -> str:
    pers = positions.get("personality", {})
    purposes = positions.get("purposes", {})
    points = [
        (pers.get("center"), "Центр", _arcana_name(pers.get("center"))),
        (pers.get("bottom"), "Карма", _arcana_name(pers.get("bottom"))),
        (purposes.get("personal"), "Предназн.", _arcana_name(purposes.get("personal"))),
    ]
    return _page(
        1,
        '<div class="mark">✦</div><h1>Матрица судьбы</h1>'
        '<div class="cover-subtitle">Персональный разбор по методу Ладини</div>'
        f'<div class="cover-name">{_e(user_name)}</div>'
        f'<div class="cover-meta">Дата рождения: {_e(_format_birth_date(birth_date))}</div>'
        '<div class="cover-points">'
        + "".join(
            f'<div class="cover-point"><div class="num">{int(num) if num is not None else "—"}</div>'
            f'<div class="label">{_e(label)}</div><div class="value">{_e(name)}</div></div>'
            for num, label, name in points
        )
        + '</div><div class="cover-line"></div>'
        f'<div class="cover-foot">СОЗДАНО ДЛЯ {_e(user_name).upper()}</div>',
        class_name="cover",
    )


_TOC_TITLES = {
    "who_you_are":   "Кто ты — характер и центр",
    "karmic_tail":   "Кармический хвост",
    "talents":       "Таланты и вдохновение",
    "purpose":       "Предназначение",
    "relationships": "Отношения",
    "finance":       "Деньги и реализация",
    "parental":      "Род и семья",
    "advice":        "Совет на этот период",
}

_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")


def _contents_page(
    section_first_pages: dict[str, int],
    glossary_page: int,
    summary_page: int,
) -> str:
    rows: list[tuple[str, str, str]] = [(_ROMAN[0], "Октаграмма судьбы", "3")]
    for idx, key in enumerate(SECTION_KEYS, start=1):
        rows.append(
            (_ROMAN[idx], _TOC_TITLES.get(key, key), str(section_first_pages.get(key, "—")))
        )
    rows.append((_ROMAN[len(SECTION_KEYS) + 1], "Краткий словарь арканов", str(glossary_page)))
    rows.append((_ROMAN[len(SECTION_KEYS) + 2], "Сводная таблица ключевых точек", str(summary_page)))
    body = _section_header("Содержание", "Что внутри отчёта")
    body += '<div class="toc-list">' + "".join(
        f'<div class="toc-row"><div class="toc-roman">{roman}</div><div class="toc-title">{_e(title)}</div><div class="toc-page">{page}</div></div>'
        for roman, title, page in rows
    ) + "</div>"
    return _page(2, body)


def _octagram_page(positions: dict[str, Any]) -> str:
    body = _section_header(
        "Октаграмма судьбы",
        "Восемь точек личностного ромба и родового квадрата",
    )
    body += f'<div class="octa-wrap">{_octagram_svg(positions)}</div>'
    body += (
        '<div class="octa-caption">Тёплое золото — личностный ромб (день, месяц, год, '
        'кармический низ + центр). Голубой — родовой квадрат. Синяя стрелка — мужская '
        'линия, красная — женская.</div>'
    )
    pers = positions.get("personality", {})
    anchors = [
        (pers.get("center"), "Центр / характер"),
        (pers.get("bottom"), "Кармический урок"),
        (pers.get("month"), "Талант / вдохновение"),
    ]
    body += '<div class="octa-anchors">' + "".join(
        f'<div class="octa-anchor"><div class="num">{int(num) if num is not None else "—"}</div>'
        f'<div class="label">{_e(label)}</div><div class="name">{_e(_arcana_name(num))}</div></div>'
        for num, label in anchors
    ) + "</div>"
    return _page(3, body)


# Map narrative section → anchor arcana (the single number that the section
# is mostly about). Keeps the section page visually anchored.
def _section_anchor(positions: dict[str, Any], section_key: str) -> int | None:
    pers = positions.get("personality", {})
    purposes = positions.get("purposes", {})
    channels = positions.get("channels", {}) or {}
    mapping = {
        "who_you_are":   pers.get("center"),
        "karmic_tail":   pers.get("bottom"),
        "talents":       pers.get("month"),
        "purpose":       purposes.get("personal"),
        "relationships": (channels.get("relationships") or [None])[0],
        "finance":       (channels.get("finance") or [None])[0],
        "parental":      (channels.get("parental") or [None])[0],
        "advice":        pers.get("center"),
    }
    val = mapping.get(section_key)
    return int(val) if isinstance(val, int) else None


def _section_arcana_trio(
    positions: dict[str, Any], section_key: str
) -> list[tuple[int, str, str]]:
    """3 ``(arcana_num, context, short_label)`` per section. Each gets a
    mini-card with meaning + plus/minus from ``arcana_meanings``.

    Picked so the section is anchored to its dominant matrix points —
    keeps the cards specific to the reader, not generic."""
    pers = positions.get("personality", {}) or {}
    sq = positions.get("ancestral_square", {}) or {}
    purposes = positions.get("purposes", {}) or {}
    channels = positions.get("channels", {}) or {}

    def _ch(name: str, idx: int) -> int | None:
        seq = channels.get(name)
        if isinstance(seq, list) and len(seq) > idx:
            return seq[idx]
        return None

    raw_map: dict[str, list[tuple[Any, str, str]]] = {
        "who_you_are": [
            (pers.get("center"),     "personality", "Центр — характер"),
            (pers.get("day"),        "personality", "День — портрет"),
            (sq.get("top_left"),     "ancestral",   "Внутренний потенциал"),
        ],
        "karmic_tail": [
            (pers.get("bottom"),     "karmic_tail",     "Главный урок"),
            (pers.get("year"),       "material_karma",  "Прошлый опыт"),
            (sq.get("bottom_left"),  "ancestral",       "Родовая карма"),
        ],
        "talents": [
            (pers.get("month"),      "talents",     "Высшая суть"),
            (sq.get("top_right"),    "ancestral",   "Талант рода"),
            (sq.get("top_left"),     "talents",     "Подача дара"),
        ],
        "purpose": [
            (purposes.get("personal"),  "purpose", "До ~40 лет"),
            (purposes.get("social"),    "purpose", "40–60 лет"),
            (purposes.get("planetary"), "purpose", "Миссия"),
        ],
        "relationships": [
            (_ch("relationships", 0), "relationships", "Вход в отношения"),
            (_ch("relationships", 1), "relationships", "Что делать"),
            (pers.get("bottom"),      "relationships", "Урок отношений"),
        ],
        "finance": [
            (_ch("finance", 0),         "finance",        "Откуда деньги"),
            (pers.get("year"),          "finance",        "Денежный канал"),
            (_ch("finance", 2),         "material_karma", "Готовый ресурс"),
        ],
        "parental": [
            (_ch("parental", 0),     "parental", "Зачем пришёл"),
            (pers.get("day"),        "parental", "Роль ребёнка"),
            (sq.get("bottom_right"), "parental", "Урок родителей"),
        ],
        "advice": [
            (pers.get("center"),         "personality", "Опора характера"),
            (purposes.get("planetary"),  "purpose",     "Миссия дальше"),
            (pers.get("month"),          "talents",     "Питание дара"),
        ],
    }
    out: list[tuple[int, str, str]] = []
    seen: set[tuple[int, str]] = set()
    for num, ctx, label in raw_map.get(section_key, []):
        if not isinstance(num, int):
            continue
        key = (num, ctx)
        if key in seen:
            continue
        seen.add(key)
        out.append((num, ctx, label))
    return out


_CONTEXT_LABEL_RU = {
    "personality":     "характер",
    "talents":         "талант",
    "purpose":         "предназначение",
    "parental":        "род.-дет.",
    "ancestral":       "род",
    "relationships":   "отношения",
    "finance":         "финансы",
    "material_karma":  "мат. карма",
    "karmic_tail":     "карма",
}


# Hardcoded practice templates — generic but actionable. Personalisation
# already comes from the LLM section text + the arcana cards above.
PRACTICE_BLOCKS = {
    "who_you_are": {
        "title": "Твои сильные стороны на каждый день",
        "items": [
            "Записывай каждый вечер 1-2 ситуации дня, где ты проявил свою «настоящую» энергию — без подстройки под чужие ожидания.",
            "Раз в неделю задавай себе вопрос: «Что я делал в эту неделю по привычке, а не по своему характеру?» Меняй одну такую привычку.",
            "Найди 2-3 человека, рядом с которыми тебе не приходится «играть». Контакт с ними — твоя точка перезагрузки.",
            "Когда чувствуешь усталость без причины — сверься с центром: что ты сейчас делаешь вопреки своей природе?",
        ],
    },
    "karmic_tail": {
        "title": "Практика проработки кармического урока",
        "items": [
            "Выпиши 3-5 ситуаций из прошлого года, в которых ты повторил один и тот же сценарий. Что у них общего?",
            "Один раз в неделю — практика «другого выбора»: в типовой ситуации поступи противоположно привычному. Заметь реакцию тела.",
            "Если урок про границы — тренируйся отказывать без оправданий («нет, не получится», без объяснений). Минимум 1 отказ в день.",
            "Если урок про доверие — тренируйся озвучивать просьбу прямо, а не намёками. Минимум 1 такая просьба в день.",
        ],
    },
    "talents": {
        "title": "Профессии и призвание — куда направить дар",
        "items": [
            "Выпиши 5 занятий, после которых ты чувствуешь не усталость, а наполнение. Это первые подсказки про твой дар.",
            "В течение месяца уделяй 30 минут в день одному из этих занятий — не для результата, а для подтверждения «это моё».",
            "Если в карте сильны творческие арканы — попробуй формат «учитель-наставник»: объясни кому-то то, что умеешь.",
            "Если сильны организационные арканы (4, 7, 11) — попробуй вести небольшой проект от старта до запуска.",
            "Не путай талант с социально одобряемой профессией. Твоё предназначение — там, где тебе легко, а не где платят больше.",
        ],
    },
    "purpose": {
        "title": "Шаги к своему предназначению",
        "items": [
            "Раз в квартал перечитывай раздел «Предназначение». До 40 — собирай навык, после 40 — выходи в социальный масштаб, после 60 — делись опытом.",
            "Поставь одну цель на этот год, которая лежит на векторе ЛП → СП → ДП — а не «потому что все так делают».",
            "Если у тебя сильное планетарное предназначение — не торопись. Оно раскрывается через все три первых этапа, не миная их.",
            "Раз в месяц — честный аудит: что из последнего месяца было «по моему вектору», а что — по чужому сценарию?",
        ],
    },
    "relationships": {
        "title": "Твой идеальный партнёр и как с ним строить",
        "items": [
            "Перечитай канал отношений в своей матрице. «Вход» — кого ты притягиваешь, «середина» — что делать в паре, «итог» — куда отношения идут.",
            "Партнёр-зеркало: 3 черты, которые тебя бесят в других, — твои собственные неприсвоенные качества. Найди их у себя.",
            "Раз в неделю — разговор «без претензий» с близким человеком: только наблюдения и просьбы, без обвинений.",
            "Если канал «застрял» в минусе (повторяющиеся болезненные сценарии) — пауза от новых отношений минимум 3 месяца, чтобы пересобрать паттерн.",
        ],
    },
    "finance": {
        "title": "5 шагов открыть денежный канал",
        "items": [
            "Шаг 1. Посмотри в матрицу: твой денежный канал — это «канал года» (правый луч). Какие 3 числа на нём?",
            "Шаг 2. Найди профессию или хобби, где задействован арканный смысл этих чисел. Не «нравится теоретически» — а «уже пробовал».",
            "Шаг 3. Минимум 90 дней одной фокусной деятельности. Деньги приходят к сосредоточенности, а не к разбросу.",
            "Шаг 4. Раз в месяц — учёт доходов и расходов вручную. Без таблиц-автоматов: рука пишет — мозг видит.",
            "Шаг 5. 10-20% дохода — на развитие в своём канале (обучение, инструменты, контакты), не «просто отложить».",
        ],
    },
    "parental": {
        "title": "Твоя задача перед родом и детьми",
        "items": [
            "Если есть дети — спроси себя: что я даю им из «здоровой» части своей родовой программы, а что бессознательно повторяю из больной?",
            "Найди свою «детскую» обиду на одного из родителей. Опиши её на бумаге одним абзацем. Один раз. Сожги или порви — символический жест важен.",
            "Раз в месяц — встреча или звонок старшим родственникам без повода и просьб. Просто послушать.",
            "Если в роду были «закрытые темы» (репрессии, потери, развод) — узнай факты. Знание расширяет канал, незнание сужает.",
        ],
    },
    "advice": {
        "title": "5 шагов на ближайшие 3 месяца + аффирмация",
        "items": [
            "Месяц 1: ежедневная микро-практика 10 минут (медитация, дыхание, прогулка молча). Без пропусков.",
            "Месяц 2: один большой шаг по своему предназначению (новый проект / навык / разговор / переезд).",
            "Месяц 3: один большой отказ — от того, что давно не твоё (отношения, привычка, договор, обязательство).",
            "В конце каждого месяца — короткий письменный отчёт: что было / что узнал о себе / что меняю.",
            "Перечитывай эту страницу раз в 3 месяца. Матрица не меняется, но твой взгляд на неё — да.",
        ],
        "affirmation": (
            "Я не борюсь со своей картой — я учусь её читать. Каждый поворот, "
            "который раньше казался ошибкой, — это страница, на которой я "
            "наконец увидел свой настоящий рисунок."
        ),
    },
}


def _render_arcana_card(
    arcana_num: int,
    context: str,
    label: str,
    arcana_meanings: dict[int, dict[str, dict[str, Any]]] | None,
) -> str:
    fields: dict[str, Any] = {}
    if arcana_meanings:
        fields = arcana_meanings.get(arcana_num, {}).get(context, {}) or {}
    meaning = str(fields.get("meaning") or "").strip()
    plus = str(fields.get("plus") or "").strip()
    minus = str(fields.get("minus") or "").strip()
    professions = str(fields.get("professions") or "").strip()
    if not meaning:
        meaning = (
            f"Аркан {arcana_num} ({_arcana_name(arcana_num)}) в контексте "
            f"«{_CONTEXT_LABEL_RU.get(context, context)}». Подробная "
            "расшифровка появится после обновления словаря."
        )
    pm_html = ""
    if plus or minus:
        bits = []
        if plus:
            bits.append(f'<span class="pl">+ </span>{_e(plus)}')
        if minus:
            bits.append(f'<span class="mn">− </span>{_e(minus)}')
        pm_html = '<p class="pm">' + "<br>".join(bits) + "</p>"
    pro_html = (
        f'<div class="pro">Профессии: {_e(professions)}</div>'
        if professions
        else ""
    )
    return (
        '<article class="arc-card">'
        f'<div class="head"><div class="num">{arcana_num}</div>'
        f'<div class="name">{_e(_arcana_name(arcana_num))}</div></div>'
        f'<div class="ctx">{_e(label)}</div>'
        f'<p class="body">{_e(meaning)}</p>'
        f'{pm_html}{pro_html}'
        "</article>"
    )


def _render_practice_block(section_key: str) -> str:
    block = PRACTICE_BLOCKS.get(section_key)
    if not block:
        return ""
    items_html = "".join(f"<li>{_e(item)}</li>" for item in block.get("items", []))
    affirm = block.get("affirmation")
    affirm_html = f'<div class="affirm">«{_e(affirm)}»</div>' if affirm else ""
    return (
        f'<section class="practice"><h3>{_e(block.get("title", ""))}</h3>'
        f'<ul>{items_html}</ul>{affirm_html}</section>'
    )


SECTION_QUOTES_RU = {
    "who_you_are":   "Характер — это не приговор, а способ дышать.",
    "karmic_tail":   "Урок повторяется, пока не научишься выбирать иначе.",
    "talents":       "Талант — там, где тебе становится легко быть собой.",
    "purpose":       "Предназначение — это направление, а не пункт назначения.",
    "relationships": "Мы притягиваем не тех, кого хотим, а тех, кому равны.",
    "finance":       "Деньги — это форма, в которой энергия возвращается обратно.",
    "parental":      "Род лечится через одного — того, кто решился увидеть.",
    "advice":        "Один шаг честно — лучше десяти, сделанных «правильно».",
}


def _narrative_pages(
    start_page: int,
    section_key: str,
    section_text: str,
    positions: dict[str, Any],
    arcana_meanings: dict[int, dict[str, dict[str, Any]]] | None,
) -> list[str]:
    """V2 narrative section. Returns one or two pages: page 1 has the
    LLM text + 3 arcana cards; if a practice block exists for this
    section, it goes on page 2 (avoids cramming everything onto one A4)."""
    label = SECTION_LABELS_RU.get(section_key, section_key)
    anchor_num = _section_anchor(positions, section_key)
    anchor_html = ""
    if anchor_num is not None:
        anchor_html = (
            '<div class="anchor">'
            f'<div class="num">{anchor_num}</div>'
            f'<div><div class="name">{_e(_arcana_name(anchor_num))}</div>'
            f'<div class="keywords">{_e(_arcana_keywords(anchor_num))}</div></div></div>'
        )
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in (section_text or "").splitlines():
        line = raw.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    if not paragraphs:
        paragraphs = [
            "Подробный текст этого раздела появится после обновления контента. "
            "Числа арканов уже рассчитаны и видны на октаграмме."
        ]

    trio = _section_arcana_trio(positions, section_key)
    cards_html = "".join(
        _render_arcana_card(num, ctx, label_, arcana_meanings)
        for num, ctx, label_ in trio
    )

    body1 = _section_header(label, "Личный разбор")
    body1 += f'<div class="section-quote">«{_e(SECTION_QUOTES_RU.get(section_key, ""))}»</div>'
    body1 += '<div class="section-card">' + anchor_html
    body1 += "".join(f'<p>{_e(p)}</p>' for p in paragraphs)
    body1 += "</div>"
    if cards_html:
        body1 += f'<div class="arc-trio">{cards_html}</div>'

    pages = [_page(start_page, body1)]

    # Page 2 — practice block (only if defined)
    practice_html = _render_practice_block(section_key)
    if practice_html:
        body2 = _section_header(label, "Практика и шаги", aside="что делать")
        body2 += practice_html
        pages.append(_page(start_page + 1, body2))
    return pages


def _summary_page(page: int, positions: dict[str, Any]) -> str:
    pers = positions.get("personality", {}) or {}
    sq = positions.get("ancestral_square", {}) or {}
    lines = positions.get("lines", {}) or {}
    purposes = positions.get("purposes", {}) or {}
    channels = positions.get("channels", {}) or {}
    specials = positions.get("specials", {}) or {}

    body = _section_header("Сводная таблица", "Ключевые точки матрицы — 36 чисел в одном месте")
    body += '<div class="summary-grid">'

    def cells(items: list[tuple[Any, str]]) -> str:
        out: list[str] = []
        for num, label in items:
            if num is None:
                continue
            out.append(
                f'<div class="summary-cell"><div class="num">{int(num)}</div>'
                f'<div class="label">{_e(label)}</div>'
                f'<div class="name">{_e(_arcana_name(num))}</div></div>'
            )
        return "".join(out)

    sections: list[tuple[str, list[tuple[Any, str]]]] = [
        ("Личностный ромб", [
            (pers.get("day"), "День"),
            (pers.get("month"), "Месяц"),
            (pers.get("year"), "Год"),
            (pers.get("bottom"), "Низ / карма"),
            (pers.get("center"), "Центр"),
        ]),
        ("Родовой квадрат", [
            (sq.get("top_left"), "Род ↖"),
            (sq.get("top_right"), "Род ↗"),
            (sq.get("bottom_right"), "Род ↘"),
            (sq.get("bottom_left"), "Род ↙"),
        ]),
        ("Линии", [
            (lines.get("sky"), "Небо"),
            (lines.get("earth"), "Земля"),
            (lines.get("father"), "Отец"),
            (lines.get("mother"), "Мать"),
        ]),
        ("Предназначения", [
            (purposes.get("personal"), "До 40"),
            (purposes.get("social"), "40–60"),
            (purposes.get("spiritual"), "После 60"),
            (purposes.get("planetary"), "Миссия"),
        ]),
        ("Семантические точки", [
            (specials.get("talent"), "Талант"),
            (specials.get("character"), "Характер"),
            (specials.get("money"), "Деньги"),
            (specials.get("love"), "Любовь"),
            (specials.get("cross"), "Крест"),
        ]),
        ("Каналы — итоговая точка", [
            ((channels.get("karmic_tail") or [None] * 3)[-1], "Кармический"),
            ((channels.get("talents") or [None] * 3)[-1], "Талантов"),
            ((channels.get("relationships") or [None] * 3)[-1], "Отношений"),
            ((channels.get("finance") or [None] * 3)[-1], "Финансов"),
            ((channels.get("material_karma") or [None] * 3)[-1], "Мат. карма"),
            ((channels.get("parental") or [None] * 3)[-1], "Род.-дет."),
        ]),
    ]

    for title, items in sections:
        body += f'<div class="summary-section">{_e(title)}</div>'
        body += cells(items)

    body += "</div>"
    return _page(page, body)


def _glossary_pages(
    start_page: int,
    arcana_meanings: dict[int, dict[str, dict[str, Any]]] | None,
) -> list[str]:
    """Mini-glossary — all 22 arcana, each as a short cell. Pulls the
    `personality` context as the short definition (gender='any'). Falls
    back to the keyword list if the row isn't seeded yet."""

    def _short_text(arcana_num: int) -> str:
        if arcana_meanings:
            fields = arcana_meanings.get(arcana_num, {}).get("personality", {})
            text = str(fields.get("meaning") or "").strip()
            if text:
                words = text.split()
                if len(words) > 36:
                    text = " ".join(words[:36]).rstrip(",.;:") + "…"
                return text
        keywords = _arcana_keywords(arcana_num)
        return f"Ключевые смыслы: {keywords}." if keywords else (
            "Подробное описание появится после обновления словаря."
        )

    # 22 cards / 2 columns ≈ 11 rows; A4 fits ~12 per page so we split
    # into 2 pages of 11 cards each.
    chunks = [list(range(1, 12)), list(range(12, 23))]
    pages: list[str] = []
    for idx, chunk in enumerate(chunks, start=0):
        body = _section_header(
            "Краткий словарь арканов",
            "22 ключевых архетипа Матрицы Судьбы",
            aside=f"{idx + 1} / {len(chunks)}",
        )
        body += '<div class="glossary-grid">'
        for arcana_num in chunk:
            body += (
                '<div class="gloss-cell"><div class="head">'
                f'<div class="num">{arcana_num}</div>'
                f'<div class="name">{_e(_arcana_name(arcana_num))}</div></div>'
                f'<div class="kw">{_e(_arcana_keywords(arcana_num))}</div>'
                f'<p>{_e(_short_text(arcana_num))}</p></div>'
            )
        body += "</div>"
        pages.append(_page(start_page + idx, body))
    return pages


def _final_page(page: int) -> str:
    body = (
        '<div class="mark">✦</div>'
        '<div class="final-copy">Матрица — не приговор и не предсказание. '
        'Это карта твоих сильных сторон, повторяющихся уроков и точек роста, '
        'к которой полезно возвращаться раз в несколько месяцев.</div>'
        '<div class="disclaimer">'
        '<h3>Важно понимать</h3>'
        '<p>Отчёт носит информационно-просветительский характер и не заменяет '
        'консультаций с врачом, психологом, юристом или финансовым советником. '
        'Решения о здоровье, деньгах и отношениях принимай, опираясь на свой '
        'опыт и здравый смысл — матрица только подсветит то, на что стоит '
        'обратить внимание.</p>'
        '<p>Авторская методика расчёта — Лариса Ладини. Авторские названия '
        'арканов взяты из книги «Матрица судьбы от А до Я».</p>'
        '</div>'
        '<div class="cover-foot">ASTRO TMA · СОЗДАНО ДЛЯ ТЕБЯ</div>'
    )
    return _page(page, body, class_name="final")


# ── Public API ──────────────────────────────────────────────────────────────


def build_destiny_matrix_pdf_html(
    user_name: str,
    birth_date: str,
    positions: dict[str, Any],
    sections: dict[str, str] | None,
    arcana_meanings: dict[int, dict[str, dict[str, Any]]] | None = None,
    gender: str | None = None,  # noqa: ARG001 — reserved for future tone-of-voice tweaks
) -> str:
    """Compose the final HTML document. Section order follows SECTION_KEYS.

    V2: narrative sections may span 2 pages each (narrative + practice).
    Page numbers are assigned sequentially as sections are built so the
    TOC / footer stays consistent regardless of the practice-block mix."""
    safe_sections = sections or {}

    narrative_start = 4  # cover(1) + toc(2) + octagram(3) → narrative starts at 4
    narrative_pages: list[str] = []
    section_first_pages: dict[str, int] = {}
    next_page = narrative_start
    for key in SECTION_KEYS:
        section_first_pages[key] = next_page
        produced = _narrative_pages(
            next_page,
            key,
            safe_sections.get(key, ""),
            positions,
            arcana_meanings,
        )
        narrative_pages.extend(produced)
        next_page += len(produced)

    glossary_start = next_page
    glossary_pages = _glossary_pages(glossary_start, arcana_meanings)
    next_page += len(glossary_pages)

    summary_page_num = next_page
    final_page_num = summary_page_num + 1

    pages = [
        _cover_page(user_name, birth_date, positions),
        _contents_page(section_first_pages, glossary_start, summary_page_num),
        _octagram_page(positions),
        *narrative_pages,
        *glossary_pages,
        _summary_page(summary_page_num, positions),
        _final_page(final_page_num),
    ]
    body = "".join(pages).replace(TOTAL_PAGES_TOKEN, str(len(pages)))
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{_css()}</style></head><body>{body}</body></html>"
    )


async def generate_destiny_matrix_pdf_html(
    user_name: str,
    birth_date: str,
    positions: dict[str, Any],
    sections: dict[str, str] | None,
    arcana_meanings: dict[int, dict[str, dict[str, Any]]] | None = None,
    gender: str | None = None,
) -> bytes:
    from playwright.async_api import async_playwright

    document = build_destiny_matrix_pdf_html(
        user_name=user_name,
        birth_date=birth_date,
        positions=positions,
        sections=sections,
        arcana_meanings=arcana_meanings,
        gender=gender,
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
