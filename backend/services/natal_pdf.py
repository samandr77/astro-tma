"""Generate a complete natal chart PDF report using ReportLab."""

from __future__ import annotations

import math
import os
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.astro.sign_cases import sign_ru as _sign_case_ru

_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
_FONT_REGISTERED = False
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

GOLD = HexColor("#d4b254")
GOLD_DIM = HexColor("#8a7a3a")
FIRE = HexColor("#ff6b35")
AIR = HexColor("#9b5cff")
WATER = HexColor("#29c4b5")
EARTH = HexColor("#78b65a")
TEXT = HexColor("#f0ecf8")
TEXT_DIM = HexColor("#b6afca")
BG = HexColor("#07060f")
BG_PANEL = HexColor("#100b22")
WHEEL_BG = HexColor("#0d132b")
SURFACE = HexColor("#0e0b20")
SURFACE_2 = HexColor("#171129")
LINE = HexColor("#2c2540")
LINE_SOFT = HexColor("#34294a")

SIGN_SYMBOLS = {
    "aries": "♈", "taurus": "♉", "gemini": "♊", "cancer": "♋",
    "leo": "♌", "virgo": "♍", "libra": "♎", "scorpio": "♏",
    "sagittarius": "♐", "capricorn": "♑", "aquarius": "♒", "pisces": "♓",
}
SIGN_RU = {
    "aries": "Овен", "taurus": "Телец", "gemini": "Близнецы", "cancer": "Рак",
    "leo": "Лев", "virgo": "Дева", "libra": "Весы", "scorpio": "Скорпион",
    "sagittarius": "Стрелец", "capricorn": "Козерог",
    "aquarius": "Водолей", "pisces": "Рыбы",
}
from services.astro.planet_names import PLANET_GLYPH as PLANET_SYMBOLS  # noqa: E402
from services.astro.planet_names import PLANET_RU  # noqa: E402

# Iteration order for the PDF planet table — only the 10 classical points so
# the page layout stays predictable. Lookups still use the full shared dict.
PLANET_ORDER = (
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
)
ASPECT_SYMBOLS = {
    "conjunction": "☌", "trine": "△", "sextile": "⚹",
    "square": "□", "opposition": "☍", "quincunx": "⚻",
}
ASPECT_RU = {
    "conjunction": "Соединение", "trine": "Трин", "sextile": "Секстиль",
    "square": "Квадрат", "opposition": "Оппозиция", "quincunx": "Квинконс",
}
ASPECT_ORDER = tuple(ASPECT_RU.keys())
ELEMENTS = {
    "fire": ("Огонь", ("aries", "leo", "sagittarius")),
    "earth": ("Земля", ("taurus", "virgo", "capricorn")),
    "air": ("Воздух", ("gemini", "libra", "aquarius")),
    "water": ("Вода", ("cancer", "scorpio", "pisces")),
}
ELEMENT_COLORS = {
    "fire": FIRE,
    "earth": EARTH,
    "air": AIR,
    "water": WATER,
}
HOUSE_TOPICS = {
    1: "личность, тело, первое впечатление и способ начинать новое",
    2: "ценности, деньги, ресурсы и чувство устойчивости",
    3: "мышление, речь, обучение, документы и близкое окружение",
    4: "дом, семья, корни, внутренняя опора и личная безопасность",
    5: "творчество, любовь, дети, удовольствие и самовыражение",
    6: "режим, здоровье, работа, навыки и повседневная эффективность",
    7: "партнёрство, договоры, близкие союзы и зеркала отношений",
    8: "кризисы, доверие, общие ресурсы, глубина и трансформация",
    9: "смыслы, вера, путешествия, высшее обучение и расширение горизонта",
    10: "карьера, статус, предназначение и видимое место в мире",
    11: "друзья, команды, проекты будущего и социальные связи",
    12: "подсознание, уединение, завершения, тонкая чувствительность и восстановление",
}
ASPECT_TOPICS = {
    "conjunction": "усиливают друг друга и работают как единый внутренний импульс",
    "trine": "поддерживают естественный поток, талант и лёгкое раскрытие качества",
    "sextile": "дают возможность, которую важно осознанно использовать",
    "square": "создают напряжение, требующее действия, роста и настройки поведения",
    "opposition": "показывают полярность, которую нужно научиться удерживать в балансе",
    "quincunx": "требуют тонкой перенастройки привычек и взгляда на ситуацию",
}

ELEMENT_COPY = {
    "fire": (
        "Действие, инициатива, страсть. Энергия просыпается, когда есть цель, риск и право проявиться.",
        ("Смелый", "Энергичный", "Прямой", "Импульсивный", "Лидер"),
    ),
    "earth": (
        "Практичность, телесность, упорство. Важны видимый результат, надежность и опора на реальность.",
        ("Надежный", "Собранный", "Практичный", "Терпеливый", "Материальный"),
    ),
    "air": (
        "Идеи, общение, легкость. Карта оживает через слова, связи, обучение и обмен смыслами.",
        ("Умный", "Общительный", "Гибкий", "Любознательный", "Свободный"),
    ),
    "water": (
        "Чувства, интуиция, глубина. Внутренние переживания становятся главным навигатором.",
        ("Чуткий", "Глубокий", "Интуитивный", "Памятливый", "Тонкий"),
    ),
}

HOUSE_LABELS = {
    1: "ЛИЧНОСТЬ И ОБЛИК",
    2: "ДЕНЬГИ И ЦЕННОСТИ",
    3: "ОБЩЕНИЕ И ОБУЧЕНИЕ",
    4: "ДОМ И КОРНИ",
    5: "ТВОРЧЕСТВО И ЛЮБОВЬ",
    6: "РАБОТА И ЗДОРОВЬЕ",
    7: "ПАРТНЕРСТВО",
    8: "ПЕРЕМЕНЫ И РЕСУРСЫ",
    9: "ФИЛОСОФИЯ И ПУТЕШЕСТВИЯ",
    10: "КАРЬЕРА И РЕПУТАЦИЯ",
    11: "СООБЩЕСТВО И ЦЕЛИ",
    12: "ВНУТРЕННЯЯ ЖИЗНЬ",
}

GLOSSARY = (
    ("Планета", "Небесное тело, отвечающее за определенную сферу психики и жизни."),
    ("Знак зодиака", "Один из 12 30-градусных секторов эклиптики."),
    ("Дом", "Сектор карты, отвечающий за конкретную сферу жизни."),
    ("Аспект", "Угловая связь между двумя планетами."),
    ("Асцендент", "Знак на восточном горизонте в момент рождения."),
    ("Ретроградность", "Период, когда планета движется обратно относительно Земли."),
)


def _register_fonts() -> None:
    """Register a Cyrillic-capable font when available, with safe built-in fallback."""
    global _FONT_REGISTERED, FONT, FONT_BOLD
    if _FONT_REGISTERED:
        return

    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/DejaVuSans.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/NotoSans-Regular.ttf",
        os.path.join(_FONT_DIR, "DejaVuSans.ttf"),
    ]
    for regular_path in regular_candidates:
        if not os.path.exists(regular_path):
            continue
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", regular_path))
            bold_path = regular_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
            if regular_path.endswith("Arial Unicode.ttf"):
                bold_path = regular_path
            pdfmetrics.registerFont(
                TTFont("DejaVu-Bold", bold_path if os.path.exists(bold_path) else regular_path)
            )
            FONT = "DejaVu"
            FONT_BOLD = "DejaVu-Bold"
            _FONT_REGISTERED = True
            return
        except Exception:
            continue

    _FONT_REGISTERED = True


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


def _sign_element(sign: Any) -> str:
    sign_key = _key(sign)
    if sign_key not in SIGN_SYMBOLS:
        reverse = {v.lower(): k for k, v in SIGN_RU.items()}
        sign_key = reverse.get(sign_key, sign_key)
    for element, (_, signs) in ELEMENTS.items():
        if sign_key in signs:
            return element
    return "fire"


def _spaced(text: str) -> str:
    return " ".join(str(text or "").upper())


def _planet_key(name: Any) -> str:
    raw = _key(name)
    reverse = {
        "солнце": "sun", "луна": "moon", "меркурий": "mercury", "венера": "venus",
        "марс": "mars", "юпитер": "jupiter", "сатурн": "saturn", "уран": "uranus",
        "нептун": "neptune", "плутон": "pluto",
    }
    return reverse.get(raw, raw)


def _aspect_key(name: Any) -> str:
    raw = _key(name)
    reverse = {
        "соединение": "conjunction", "трин": "trine", "секстиль": "sextile",
        "квадрат": "square", "оппозиция": "opposition", "квинконс": "quincunx",
    }
    return reverse.get(raw, raw)


def _deg_str(deg: float | int | None, *, within_sign: bool = True) -> str:
    value = float(deg or 0)
    if within_sign:
        value = value % 30
    d = int(value)
    m = int((value - d) * 60)
    return f"{d}°{m:02d}'"


def _new_page(c: canvas.Canvas, w: float, h: float) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.saveState()
    c.setFillColor(GOLD_DIM)
    for sx, sy, size in (
        (78, h - 108, 1.1), (145, h - 160, 0.7), (w - 145, h - 194, 0.9),
        (w - 78, h - 266, 0.7), (92, 142, 0.7), (w - 110, 118, 0.8),
    ):
        c.circle(sx, sy, size, stroke=0, fill=1)
    c.restoreState()


def _set_font(c: canvas.Canvas, bold: bool, size: int | float) -> None:
    c.setFont(FONT_BOLD if bold else FONT, size)


def _draw_footer(c: canvas.Canvas, w: float) -> None:
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 10)
    c.drawCentredString(w / 2, 32, "Astro TMA · персональный астрологический отчёт")


def _ensure_space(c: canvas.Canvas, y: float, needed: float, w: float, h: float) -> float:
    if y - needed >= 58:
        return y
    _draw_footer(c, w)
    c.showPage()
    _new_page(c, w, h)
    return h - 56


def _wrap_paragraph(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_chars: int,
    line_h: int,
    bottom: int,
    w: float,
    h: float,
) -> float:
    words = str(text or "").split()
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if len(test) > max_chars and line:
            c.drawString(x, y, line)
            y -= line_h
            line = word
            if y < bottom:
                _draw_footer(c, w)
                c.showPage()
                _new_page(c, w, h)
                y = h - 56
                c.setFillColor(TEXT)
                _set_font(c, False, 11)
        else:
            line = test
    if line:
        c.drawString(x, y, line)
        y -= line_h
    return y


def _lines(text: str, max_chars: int, max_lines: int | None = None) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    result: list[str] = []
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if len(test) > max_chars and line:
            result.append(line)
            line = word
            if max_lines and len(result) >= max_lines:
                break
        else:
            line = test
    if line and (not max_lines or len(result) < max_lines):
        result.append(line)
    if max_lines and len(result) == max_lines and len(" ".join(words)) > len(" ".join(result)):
        result[-1] = result[-1].rstrip(" .") + "."
    return result


def _draw_wrapped_static(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_chars: int,
    line_h: int,
    max_lines: int | None = None,
) -> float:
    for line in _lines(text, max_chars, max_lines):
        c.drawString(x, y, line)
        y -= line_h
    return y


def _lines_for_width(
    c: canvas.Canvas,
    text: str,
    max_width: float,
    *,
    bold: bool,
    size: float,
    max_lines: int | None = None,
) -> list[str]:
    font_name = FONT_BOLD if bold else FONT
    words = str(text or "").replace("\n", " ").split()
    result: list[str] = []
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if line and c.stringWidth(test, font_name, size) > max_width:
            result.append(line)
            line = word
            if max_lines and len(result) >= max_lines:
                break
        else:
            line = test
    if line and (not max_lines or len(result) < max_lines):
        result.append(line)
    if max_lines and len(result) == max_lines and len(" ".join(words)) > len(" ".join(result)):
        result[-1] = result[-1].rstrip(" .,:;—-") + "."
    return result


def _limit_words(text: str, words: int) -> str:
    parts = str(text or "").split()
    if len(parts) <= words:
        return " ".join(parts)
    return " ".join(parts[:words]).rstrip(" .,:;—-") + "."


def _draw_card_frame(c: canvas.Canvas, x: float, y: float, width: float, height: float) -> None:
    c.setFillColor(SURFACE)
    c.roundRect(x, y - height, width, height, 10, stroke=0, fill=1)
    c.setStrokeColor(LINE_SOFT)
    c.setLineWidth(0.45)
    c.roundRect(x, y - height, width, height, 10, stroke=1, fill=0)
    c.setStrokeColor(GOLD_DIM)
    c.setLineWidth(0.35)
    c.line(x + 14, y - 34, x + width - 14, y - 34)


def _compact_description(entry: Any, fallback: str, *, words: int = 42) -> str:
    if isinstance(entry, dict):
        source = str(entry.get("full") or entry.get("short") or "").strip()
    else:
        source = ""
    fallback = str(fallback or "").strip()
    if source and fallback and len(source.split()) < max(18, words // 2):
        source = f"{source} {fallback}"
    source = source or fallback
    parts = source.split()
    if len(parts) <= words:
        return source
    return " ".join(parts[:words]).rstrip(" .,;:") + "."


def _roman(num: int) -> str:
    values = (
        (10, "X"), (9, "IX"), (8, "VIII"), (7, "VII"), (6, "VI"),
        (5, "V"), (4, "IV"), (1, "I"),
    )
    out = ""
    rest = num
    for value, glyph in values:
        while rest >= value:
            out += glyph
            rest -= value
    return out


def _page_footer(c: canvas.Canvas, w: float, page: int, total: int | None = None) -> None:
    c.setStrokeColor(LINE)
    c.setLineWidth(0.45)
    c.line(62, 54, w - 62, 54)
    c.setFillColor(GOLD_DIM)
    c.circle(w / 2, 54, 1.6, stroke=0, fill=1)
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 10)
    suffix = f"{page} / {total}" if total else str(page)
    c.drawCentredString(w / 2, 32, f"ASTRO TMA · НАТАЛЬНАЯ КАРТА {suffix}")


def _aspect_kind(aspect_type: str) -> str:
    if aspect_type in ("trine", "sextile"):
        return "harmonious"
    if aspect_type in ("square", "opposition"):
        return "challenging"
    return "neutral"


def _element_percentages(planets: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = _element_counts(planets)
    total = max(sum(counts.values()), 1)
    return {key: round(value / total * 100) for key, value in counts.items()}


def _sign_abs_degree(sign: Any) -> float:
    sign_order = list(SIGN_RU.keys())
    key = _key(sign)
    return float(sign_order.index(key) * 30) if key in sign_order else 0.0


def _chart_abs_degree(point: dict[str, Any]) -> float:
    if "degree" in point and point.get("degree") is not None:
        return float(point.get("degree") or 0) % 360
    return (_sign_abs_degree(point.get("sign")) + float(point.get("sign_degree") or 0)) % 360


def _ascendant_degree(houses: list[dict[str, Any]], asc_sign: str | None) -> float:
    for house in houses:
        if int(house.get("number") or 0) == 1:
            return _chart_abs_degree(house)
    return _sign_abs_degree(asc_sign)


def _wheel_angle(abs_degree: float, ascendant_degree: float) -> float:
    # Match the app's reference wheel: the Ascendant sits at 9 o'clock.
    return 180 + (abs_degree - ascendant_degree)


def _polar_point(cx: float, cy: float, radius: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius


def _draw_title(c: canvas.Canvas, title: str, w: float, h: float, subtitle: str | None = None) -> float:
    _new_page(c, w, h)
    c.setFillColor(GOLD)
    _set_font(c, True, 22)
    c.drawString(40, h - 52, title)
    y = h - 82
    if subtitle:
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 12)
        y = _wrap_paragraph(c, subtitle, 40, y, 82, 15, 58, w, h)
        y -= 10
    return y


def _description(entry: Any, fallback: str) -> str:
    if isinstance(entry, dict):
        text = str(entry.get("full") or entry.get("short") or "").strip()
        if text:
            return text
    return fallback


def _planet_fallback(name: str, planet: dict[str, Any]) -> str:
    ru = PLANET_RU.get(name, name)
    sign = planet.get("sign_ru") or planet.get("sign")
    sign_prep = _sign_ru_case(sign, "prep")
    sign_gen = _sign_ru_case(sign, "gen")
    house = planet.get("house") or "?"
    retro = " Ретроградность делает проявление более внутренним и требует времени на осмысление." if planet.get("retrograde") else ""
    return (
        f"{ru} в {sign_prep} показывает, как эта часть личности проявляется в характере, "
        f"повседневных выборах, отношениях и делах. В знаке {sign_gen} планета раскрывает "
        f"свой стиль через привычные реакции, сильные стороны, уязвимости и повторяющиеся "
        f"жизненные сценарии. Положение в {house}-м доме связывает эту тему с конкретной "
        f"сферой жизни, где она становится особенно заметной и требует осознанности.{retro}"
    )


def _house_fallback(house: dict[str, Any]) -> str:
    num = int(house.get("number") or 0)
    sign = house.get("sign_ru") or house.get("sign")
    sign_nom = _sign_ru(sign)
    sign_prep = _sign_ru_case(sign, "prep")
    topic = HOUSE_TOPICS.get(num, "важную сферу жизненного опыта")
    return (
        f"{num}-й дом описывает {topic}. Знак на куспиде — {sign_nom}; дом в {sign_prep} показывает, в каком "
        f"стиле эта область раскрывается: через привычные реакции, выборы и повторяющиеся "
        f"жизненные обстоятельства. Этот раздел помогает увидеть, где стоит действовать "
        f"смелее, а где полезнее сохранять устойчивость и наблюдательность."
    )


def _aspect_fallback(aspect: dict[str, Any]) -> str:
    p1_key = _planet_key(aspect.get("p1"))
    p2_key = _planet_key(aspect.get("p2"))
    aspect_type = _aspect_key(aspect.get("aspect"))
    p1 = PLANET_RU.get(p1_key, str(aspect.get("p1") or "Планета"))
    p2 = PLANET_RU.get(p2_key, str(aspect.get("p2") or "Планета"))
    topic = ASPECT_TOPICS.get(aspect_type, "создают важную внутреннюю связь")
    return (
        f"{p1} и {p2} {topic}. Этот аспект показывает, как разные части вашей "
        f"психики договариваются между собой: где возникает естественная поддержка, "
        f"а где требуется взрослая настройка реакции. Чем точнее орб, тем заметнее "
        f"эта тема проявляется в характере, отношениях и выборе направления."
    )


def _aspect_description_map(descriptions: dict[str, Any] | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    items = ((descriptions or {}).get("aspects") or [])
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        p1 = _planet_key(entry.get("p1"))
        p2 = _planet_key(entry.get("p2"))
        atype = _aspect_key(entry.get("type") or entry.get("aspect"))
        if p1 and p2 and atype:
            out[(p1, p2, atype)] = entry
            out[(p2, p1, atype)] = entry
    return out


def _render_items_section(
    c: canvas.Canvas,
    w: float,
    h: float,
    title: str,
    subtitle: str,
    items: list[tuple[str, str]],
) -> None:
    y = _draw_title(c, title, w, h, subtitle)
    for header, paragraph in items:
        y = _ensure_space(c, y, 88, w, h)
        c.setFillColor(GOLD)
        _set_font(c, True, 14)
        c.drawString(40, y, header)
        y -= 18
        c.setFillColor(TEXT)
        _set_font(c, False, 12)
        y = _wrap_paragraph(c, paragraph, 40, y, 82, 15, 58, w, h)
        y -= 12
    _draw_footer(c, w)
    c.showPage()


def _element_counts(planets: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {element: 0 for element in ELEMENTS}
    for planet in planets.values():
        sign = _key(planet.get("sign"))
        for element, (_, signs) in ELEMENTS.items():
            if sign in signs:
                counts[element] += 1
                break
    return counts


def generate_natal_pdf(
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
    """Generate a complete natal chart PDF and return it as bytes."""
    _register_fonts()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    page = 1
    total_hint = None
    planet_desc = (descriptions or {}).get("planets") or {}
    house_desc = (descriptions or {}).get("houses") or {}
    aspect_desc = _aspect_description_map(descriptions)

    def finish_page() -> None:
        nonlocal page
        _page_footer(c, w, page, total_hint)
        c.showPage()
        page += 1

    def title_page(title: str, subtitle: str) -> float:
        _new_page(c, w, h)
        c.setFillColor(GOLD)
        _set_font(c, True, 20)
        title_y = h - 82
        for line in _lines_for_width(c, title, w - 116, bold=True, size=20, max_lines=2):
            c.drawString(58, title_y, line)
            title_y -= 24
        c.setStrokeColor(GOLD_DIM)
        c.setLineWidth(0.5)
        rule_y = title_y + 6
        c.line(58, rule_y, w - 58, rule_y)
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 10.5)
        subtitle_y = rule_y - 29
        for line in _lines_for_width(c, subtitle, w - 116, bold=False, size=10.5, max_lines=2):
            c.drawString(58, subtitle_y, line)
            subtitle_y -= 14
        return subtitle_y - 32

    def draw_wheel(cx: float, cy: float, radius: float) -> None:
        asc_deg = _ascendant_degree(houses, asc_sign)
        outer_r = radius
        middle_r = radius * 0.82
        inner_r = radius * 0.61
        aspect_outer_r = inner_r - 10
        aspect_inner_r = inner_r - 76
        aspect_r = inner_r - 58
        planet_band_r = (aspect_outer_r + aspect_inner_r) / 2

        # Outer reference-wheel ornament, matching the app's "Моя карта" rhythm.
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.circle(cx, cy, outer_r + 38, stroke=1, fill=0)
        c.setStrokeColor(GOLD_DIM)
        c.setLineWidth(0.65)
        c.circle(cx, cy, outer_r + 28, stroke=1, fill=0)
        c.setStrokeColor(LINE)
        c.circle(cx, cy, outer_r + 9, stroke=1, fill=0)

        # Degree ticks every 5 degrees, longer at sign boundaries.
        for degree in range(0, 360, 5):
            angle = _wheel_angle(degree, asc_deg)
            is_major = degree % 30 == 0
            tick_start = _polar_point(cx, cy, outer_r + 28, angle)
            tick_end = _polar_point(cx, cy, outer_r + (38 if is_major else 34), angle)
            c.setStrokeColor(GOLD_DIM)
            c.setLineWidth(0.55 if is_major else 0.3)
            c.line(*tick_start, *tick_end)

        # Master circles.
        c.setStrokeColor(TEXT_DIM)
        c.setLineWidth(0.9)
        c.circle(cx, cy, outer_r, stroke=1, fill=0)
        c.circle(cx, cy, middle_r, stroke=1, fill=0)
        c.setLineWidth(0.75)
        c.circle(cx, cy, inner_r, stroke=1, fill=0)

        # Zodiac ring boundaries and glyphs.
        sign_keys = list(SIGN_RU.keys())
        for i, sign in enumerate(sign_keys):
            boundary = _wheel_angle(i * 30, asc_deg)
            boundary_start = _polar_point(cx, cy, middle_r, boundary)
            boundary_end = _polar_point(cx, cy, outer_r + 28, boundary)
            c.setStrokeColor(TEXT_DIM)
            c.setLineWidth(0.65)
            c.line(*boundary_start, *boundary_end)

            mid = _wheel_angle(i * 30 + 15, asc_deg)
            gx, gy = _polar_point(cx, cy, (outer_r + middle_r) / 2, mid)
            c.setFillColor(TEXT_DIM)
            _set_font(c, False, 17)
            c.drawCentredString(gx, gy - 5, SIGN_SYMBOLS.get(sign, ""))

        # House cusps and roman numerals.
        ordered_houses = sorted(
            [house for house in houses if int(house.get("number") or 0)],
            key=lambda house: int(house.get("number") or 0),
        )
        for index, house in enumerate(ordered_houses):
            num = int(house.get("number") or 0)
            cusp_degree = _chart_abs_degree(house)
            angle = _wheel_angle(cusp_degree, asc_deg)
            cusp_start = _polar_point(cx, cy, inner_r, angle)
            cusp_end = _polar_point(cx, cy, middle_r, angle)
            is_axis = num in (1, 4, 7, 10)
            c.setStrokeColor(GOLD if is_axis else LINE)
            c.setLineWidth(0.9 if is_axis else 0.45)
            c.line(*cusp_start, *cusp_end)

            next_house = ordered_houses[(index + 1) % len(ordered_houses)] if ordered_houses else house
            next_degree = _chart_abs_degree(next_house)
            span = (next_degree - cusp_degree) % 360
            mid_degree = (cusp_degree + span / 2) % 360
            tx, ty = _polar_point(cx, cy, (middle_r + inner_r) / 2, _wheel_angle(mid_degree, asc_deg))
            c.setFillColor(TEXT_DIM)
            _set_font(c, False, 11)
            c.drawCentredString(tx, ty - 3, _roman(num))

        # Planet band with equal display slots, like the reference wheel.
        planet_items = [name for name in PLANET_ORDER if planets.get(name)]
        slot_count = max(len(planet_items), 1)
        c.setStrokeColor(GOLD_DIM)
        c.setLineWidth(0.35)
        c.circle(cx, cy, aspect_outer_r, stroke=1, fill=0)
        c.circle(cx, cy, aspect_inner_r, stroke=1, fill=0)
        for index in range(slot_count):
            angle = _wheel_angle(index * (360 / slot_count), asc_deg)
            slot_start = _polar_point(cx, cy, aspect_inner_r, angle)
            slot_end = _polar_point(cx, cy, aspect_outer_r, angle)
            c.setStrokeColor(GOLD_DIM)
            c.setLineWidth(0.25)
            c.line(*slot_start, *slot_end)

        planet_points: dict[str, tuple[float, float]] = {}
        for index, name in enumerate(planet_items):
            display_degree = index * (360 / slot_count)
            angle = _wheel_angle(display_degree, asc_deg)
            px, py = _polar_point(cx, cy, planet_band_r, angle)
            planet_points[name] = _polar_point(cx, cy, aspect_r, angle)
            c.setFillColor(BG)
            c.setStrokeColor(GOLD_DIM)
            c.setLineWidth(0.45)
            c.circle(px, py, 12, stroke=1, fill=1)
            c.setFillColor(GOLD)
            _set_font(c, True, 14)
            c.drawCentredString(px, py - 4, PLANET_SYMBOLS.get(name, ""))
            if planets[name].get("retrograde"):
                c.setFillColor(TEXT_DIM)
                _set_font(c, False, 10)
                c.drawCentredString(px + 10, py + 8, "℞")

        # Only the strongest aspect lines inside the center, to keep the wheel readable.
        c.setLineWidth(0.6)
        for aspect in sorted(aspects, key=lambda a: float(a.get("orb") or 99))[:6]:
            p1_key = _planet_key(aspect.get("p1"))
            p2_key = _planet_key(aspect.get("p2"))
            aspect_type = _aspect_key(aspect.get("aspect"))
            if p1_key not in planet_points or p2_key not in planet_points:
                continue
            if aspect_type == "trine":
                c.setStrokeColor(WATER)
                c.setDash()
            elif aspect_type == "square":
                c.setStrokeColor(FIRE)
                c.setDash()
            elif aspect_type == "opposition":
                c.setStrokeColor(AIR)
                c.setDash(2, 3)
            elif aspect_type == "sextile":
                c.setStrokeColor(EARTH)
                c.setDash(2, 2)
            else:
                c.setStrokeColor(GOLD_DIM)
                c.setDash()
            c.line(*planet_points[p1_key], *planet_points[p2_key])
            c.setDash()
            c.setFillColor(GOLD)
            c.circle(*planet_points[p1_key], 1.1, stroke=0, fill=1)
            c.circle(*planet_points[p2_key], 1.1, stroke=0, fill=1)

    # 1. Cover.
    _new_page(c, w, h)
    c.setStrokeColor(GOLD_DIM)
    c.setLineWidth(0.75)
    c.circle(w / 2, h - 176, 86, stroke=1, fill=0)
    c.setLineWidth(0.45)
    c.circle(w / 2, h - 176, 56, stroke=1, fill=0)
    for angle in range(0, 360, 30):
        x1, y1 = _polar_point(w / 2, h - 176, 62, angle)
        x2, y2 = _polar_point(w / 2, h - 176, 82, angle)
        c.line(x1, y1, x2, y2)
    c.setFillColor(GOLD)
    _set_font(c, True, 36)
    c.drawCentredString(w / 2, h - 188, "✦")
    _set_font(c, True, 27)
    c.drawCentredString(w / 2, h - 304, _spaced("Натальная карта"))
    c.setFillColor(TEXT)
    _set_font(c, False, 15)
    c.drawCentredString(w / 2, h - 334, "Персональный астрологический отчёт")
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 12.5)
    c.drawCentredString(w / 2, h - 398, user_name or "Пользователь")
    c.drawCentredString(w / 2, h - 420, f"{birth_date or 'Дата не указана'} · {birth_time or 'время не указано'}")
    c.drawCentredString(w / 2, h - 442, birth_city or "Город не указан")
    key_points = [("☉ СОЛНЦЕ", _sign_ru(sun_sign)), ("☽ ЛУНА", _sign_ru(moon_sign))]
    if asc_sign:
        key_points.append(("↑ ВОСХОД", _sign_ru(asc_sign)))
    key_point_x = 120
    for point_label, point_value in key_points:
        c.setFillColor(GOLD)
        _set_font(c, True, 18)
        c.drawCentredString(key_point_x, h - 523, point_label.split()[0])
        _set_font(c, False, 10.5)
        c.drawCentredString(key_point_x, h - 552, _spaced(point_label.split(maxsplit=1)[1]))
        c.setFillColor(TEXT)
        _set_font(c, False, 16.5)
        c.drawCentredString(key_point_x, h - 580, point_value)
        key_point_x += 178
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 10)
    c.drawCentredString(w / 2, 52, f"A S T R O  T M A  ·  M A D E  F O R  {_spaced(user_name or 'USER')}")
    c.showPage()
    page += 1

    # 2. Contents.
    y = title_page("Содержание", "Что внутри отчёта")
    contents = (
        ("I", "Ключевые точки карты", "3"),
        ("II", "Натальное колесо", "4"),
        ("III", "Баланс стихий и характер", "5"),
        ("IV", "Планеты в знаках", "6"),
        ("V", "Дома гороскопа", "9"),
        ("VI", "Аспекты — связи между планетами", "11"),
        ("VII", "Персональная интерпретация", "12"),
    )
    for content_marker, content_title, content_page in contents:
        c.setStrokeColor(LINE)
        c.setLineWidth(0.25)
        c.line(58, y - 22, w - 58, y - 22)
        c.setFillColor(GOLD_DIM)
        _set_font(c, True, 13)
        c.drawString(58, y - 2, content_marker)
        c.setFillColor(TEXT)
        _set_font(c, False, 14)
        c.drawString(94, y - 2, content_title)
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 12)
        c.drawRightString(w - 58, y - 2, content_page)
        y -= 50
    finish_page()

    # 3. Key points.
    y = title_page("Ключевые точки", "Три центра, через которые читается ваша карта")
    card_w = 160
    card_h = 245
    cards = [
        ("☉", "СОЛНЦЕ", _sign_ru(sun_sign), "Как я сияю", "Солнце показывает волю, главный вектор личности и способ быть видимым."),
        ("☽", "ЛУНА", _sign_ru(moon_sign), "Что я чувствую", "Луна описывает эмоции, привычные реакции и внутренний способ восстанавливаться."),
        ("↑", "ВОСХОД", _sign_ru(asc_sign) if asc_sign else "не рассчитан", "Как меня видят", "Асцендент показывает первое впечатление, стиль входа в мир и телесный образ."),
    ]
    for i, (glyph, card_label, card_value, quote, text) in enumerate(cards):
        card_x = 40 + i * (card_w + 18)
        c.setFillColor(SURFACE)
        c.roundRect(card_x, y - card_h, card_w, card_h, 9, fill=1, stroke=0)
        c.setStrokeColor(LINE_SOFT)
        c.setLineWidth(0.45)
        c.roundRect(card_x, y - card_h, card_w, card_h, 9, fill=0, stroke=1)
        c.setFillColor(GOLD)
        _set_font(c, True, 25)
        c.drawCentredString(card_x + card_w / 2, y - 42, glyph)
        _set_font(c, True, 10)
        c.drawCentredString(card_x + card_w / 2, y - 74, _spaced(card_label))
        element = _sign_element(card_value)
        c.setFillColor(ELEMENT_COLORS[element])
        c.circle(card_x + card_w / 2, y - 105, 12, stroke=0, fill=1)
        c.setFillColor(TEXT)
        _set_font(c, True, 15)
        c.drawCentredString(card_x + card_w / 2, y - 110, _sign_symbol(card_value))
        c.setFillColor(TEXT)
        _set_font(c, False, 15)
        c.drawCentredString(card_x + card_w / 2, y - 140, card_value)
        c.setStrokeColor(GOLD_DIM)
        c.setLineWidth(0.35)
        c.line(card_x + 58, y - 162, card_x + card_w - 58, y - 162)
        c.setFillColor(GOLD_DIM)
        _set_font(c, False, 10)
        c.drawCentredString(card_x + card_w / 2, y - 184, f"«{quote}»")
        c.setFillColor(TEXT)
        _set_font(c, False, 10.5)
        _draw_wrapped_static(c, text, card_x + 16, y - 210, 24, 14, 4)
    perc = _element_percentages(planets)
    dominant = max(perc, key=lambda element: perc[element]) if perc else "fire"
    dom_label = ELEMENTS[dominant][0]
    c.setFillColor(SURFACE)
    c.roundRect(58, 148, w - 116, 112, 8, stroke=0, fill=1)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.roundRect(58, 148, w - 116, 112, 8, stroke=1, fill=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.3)
    c.line(58, 148, 58, 260)
    c.setFillColor(ELEMENT_COLORS.get(dominant, GOLD))
    _set_font(c, True, 20)
    c.drawString(82, 213, "△")
    c.setFillColor(GOLD)
    _set_font(c, True, 15)
    c.drawString(132, 224, f"Доминирует {dom_label.lower()}")
    c.setFillColor(TEXT)
    _set_font(c, False, 12)
    c.drawString(132, 204, f"{perc.get(dominant, 0)}% карты")
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 12)
    _draw_wrapped_static(c, ELEMENT_COPY[dominant][0], 78, 178, 74, 15, 2)
    finish_page()

    # 4. Wheel.
    y = title_page("Натальное колесо", "Карта неба в момент вашего рождения")
    wheel_size = 488
    wheel_x = (w - wheel_size) / 2
    wheel_y = 160
    c.setFillColor(WHEEL_BG)
    c.rect(wheel_x, wheel_y, wheel_size, wheel_size, stroke=0, fill=1)
    c.saveState()
    try:
        c.setFillAlpha(0.18)
    except Exception:
        pass
    c.setFillColor(HexColor("#23324f"))
    for angle in (18, 78, 138, 198, 258, 318):
        p0 = _polar_point(w / 2, wheel_y + wheel_size / 2, 70, angle)
        p1 = _polar_point(w / 2, wheel_y + wheel_size / 2, 222, angle - 14)
        p2 = _polar_point(w / 2, wheel_y + wheel_size / 2, 222, angle + 14)
        path = c.beginPath()
        path.moveTo(*p0)
        path.lineTo(*p1)
        path.lineTo(*p2)
        path.close()
        c.drawPath(path, stroke=0, fill=1)
    c.restoreState()
    draw_wheel(w / 2, wheel_y + wheel_size / 2, 176)
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 11)
    legend_y = 104
    legends = (
        ("☌", "Соединение · слияние"),
        ("△", "Трин · поток"),
        ("⚹", "Секстиль · возможность"),
        ("□", "Квадрат · вызов"),
        ("☍", "Оппозиция · противостояние"),
        ("⚻", "Квинконс · пересборка"),
    )
    for i, (glyph, label) in enumerate(legends):
        c.drawString(80 + (i % 2) * 240, legend_y - (i // 2) * 20, f"{glyph} {label}")
    finish_page()

    # 5. Elements.
    y = title_page("Баланс стихий", "Как распределена энергия вашей карты")
    for element in ELEMENTS:
        element_label = ELEMENTS[element][0]
        pct = perc.get(element, 0)
        c.setFillColor(TEXT)
        _set_font(c, True, 14)
        c.drawString(58, y, element_label)
        c.drawRightString(156, y, f"{pct}%")
        c.setFillColor(LINE)
        c.roundRect(180, y - 5, 300, 8, 4, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.roundRect(180, y - 5, 300 * pct / 100, 8, 4, fill=1, stroke=0)
        y -= 42
    y -= 10
    for element in ELEMENTS:
        element_label = ELEMENTS[element][0]
        pct = perc.get(element, 0)
        c.setFillColor(GOLD)
        _set_font(c, True, 14)
        c.drawString(58, y, f"{element_label} {pct}%")
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 12)
        y = _draw_wrapped_static(c, ELEMENT_COPY[element][0], 58, y - 20, 60, 15, 3)
        y -= 12
    tags = ELEMENT_COPY[dominant][1]
    tag_x = 58.0
    for tag in tags:
        c.setFillColor(SURFACE_2)
        c.roundRect(tag_x, 72, len(tag) * 6.2 + 18, 22, 11, fill=1, stroke=0)
        c.setFillColor(TEXT)
        _set_font(c, False, 10.5)
        c.drawCentredString(tag_x + len(tag) * 3.1 + 9, 79, tag)
        tag_x += len(tag) * 6.2 + 26
    finish_page()

    # 6-8. Planets, paginated for longer descriptions.
    planet_items = [name for name in PLANET_ORDER if planets.get(name)]
    planet_chunks = [planet_items[index:index + 4] for index in range(0, len(planet_items), 4)]
    for chunk_index, planet_chunk in enumerate(planet_chunks, start=1):
        if not planet_chunk:
            continue
        y = title_page(f"Планеты в знаках {chunk_index} / {len(planet_chunks)}", "Где находится каждая планета и что это значит")
        for name in planet_chunk:
            planet = planets[name]
            sign = _key(planet.get("sign"))
            sign_degree = planet.get("sign_degree", planet.get("degree", 0))
            retro = " ℞ РЕТРО" if planet.get("retrograde") else ""
            _draw_card_frame(c, 44, y + 18, w - 88, 124)
            c.setFillColor(GOLD)
            _set_font(c, True, 15)
            c.drawString(62, y, f"{PLANET_SYMBOLS[name]} {PLANET_RU[name]} в {_sign_ru(sign)}")
            if retro:
                c.setFillColor(GOLD_DIM)
                _set_font(c, True, 10)
                c.drawString(62, y - 15, retro.strip())
            c.setFillColor(TEXT_DIM)
            _set_font(c, False, 10.5)
            c.drawRightString(w - 62, y, f"{_roman(int(planet.get('house') or 0))} дом · {_deg_str(sign_degree)}")
            text = _compact_description(planet_desc.get(name), _planet_fallback(name, planet), words=90)
            c.setFillColor(TEXT)
            _set_font(c, False, 11.3)
            _draw_wrapped_static(c, text, 62, y - 46, 68, 13, 5)
            y -= 138
        finish_page()

    # Houses.
    axis_labels = {1: "Асцендент", 4: "Основание (IC)", 7: "Десцендент", 10: "Середина неба (MC)"}
    col_x = (42, 305)
    house_items = [house for house in houses if int(house.get("number") or 0)]
    house_chunks = [house_items[index:index + 6] for index in range(0, len(house_items), 6)]
    for chunk_index, house_chunk in enumerate(house_chunks, start=1):
        y = title_page(f"Дома гороскопа {chunk_index} / {len(house_chunks)}", "12 сфер жизни и их обстановка")
        for house_index, house in enumerate(house_chunk):
            num = int(house.get("number") or 0)
            if house_index == 3:
                y = h - 174
            house_x = col_x[0 if house_index < 3 else 1]
            sign = _key(house.get("sign"))
            c.setFillColor(GOLD)
            _set_font(c, True, 14)
            c.drawString(house_x, y, f"{_roman(num)} {SIGN_SYMBOLS.get(sign, '')} {_sign_ru(sign)}")
            c.setFillColor(TEXT_DIM)
            _set_font(c, False, 10)
            c.drawString(house_x + 112, y, _deg_str(house.get("degree"), within_sign=False))
            if num in axis_labels:
                c.drawString(house_x, y - 13, axis_labels[num])
            c.setFillColor(TEXT)
            _set_font(c, True, 10)
            c.drawString(house_x, y - 30, HOUSE_LABELS.get(num, f"ДОМ {num}"))
            text = _compact_description(house_desc.get(str(num)), _house_fallback(house), words=64)
            c.setFillColor(TEXT_DIM)
            _set_font(c, False, 10.5)
            _draw_wrapped_static(c, text, house_x, y - 45, 29, 12, 6)
            y -= 135
        finish_page()

    # Aspects, paginated.
    grouped = [(atype, [a for a in aspects if _aspect_key(a.get("aspect")) == atype]) for atype in ASPECT_ORDER]
    grouped = [(atype, group) for atype, group in grouped if group]
    total_aspects = sum(len(group) for _, group in grouped)
    harm = sum(1 for a in aspects if _aspect_kind(_aspect_key(a.get("aspect"))) == "harmonious")
    chall = sum(1 for a in aspects if _aspect_kind(_aspect_key(a.get("aspect"))) == "challenging")
    neutral = max(total_aspects - harm - chall, 0)
    y = title_page("Аспекты", "Связи между планетами вашей карты")
    for metric_x, metric_value, metric_label in ((54, total_aspects, "ВСЕГО"), (178, harm, "ГАРМОНИЧНЫХ"), (328, chall, "НАПРЯЖЕННЫХ"), (470, neutral, "НЕЙТРАЛЬНЫХ")):
        c.setFillColor(GOLD)
        _set_font(c, True, 20)
        c.drawCentredString(metric_x, y, str(metric_value))
        c.setFillColor(TEXT_DIM)
        _set_font(c, True, 11)
        c.drawCentredString(metric_x, y - 16, metric_label)
    y -= 58
    for aspect_type, group in grouped:
        group_title = f"{ASPECT_SYMBOLS.get(aspect_type, '')} {ASPECT_RU[aspect_type].upper()} — {ASPECT_TOPICS.get(aspect_type, 'связь энергий')}"
        group_lines = _lines_for_width(c, group_title, w - 96, bold=True, size=13, max_lines=2)
        group_height = 16 * len(group_lines) + 10
        if y - group_height < 86:
            finish_page()
            y = title_page("Аспекты", "Продолжение списка связей между планетами")
        c.setFillColor(GOLD)
        _set_font(c, True, 13)
        for line in group_lines:
            c.drawString(48, y, line)
            y -= 16
        y -= 8
        for aspect in group:
            p1_key = _planet_key(aspect.get("p1"))
            p2_key = _planet_key(aspect.get("p2"))
            orb = float(aspect.get("orb") or 0)
            card_x = 52
            card_w = w - 104
            title = (
                f"{PLANET_SYMBOLS.get(p1_key, '')} {PLANET_RU.get(p1_key, aspect.get('p1', ''))} "
                f"{ASPECT_SYMBOLS.get(aspect_type, '')} "
                f"{PLANET_SYMBOLS.get(p2_key, '')} {PLANET_RU.get(p2_key, aspect.get('p2', ''))}"
            )
            title_lines = _lines_for_width(c, title, card_w - 92, bold=True, size=12, max_lines=2)
            desc = _compact_description(aspect_desc.get((p1_key, p2_key, aspect_type)), _aspect_fallback(aspect), words=76)
            desc_lines = _lines_for_width(c, desc, card_w - 34, bold=False, size=11, max_lines=4)
            card_h = 32 + 15 * len(title_lines) + 13 * len(desc_lines)
            if y - card_h < 66:
                finish_page()
                y = title_page("Аспекты", "Продолжение списка связей между планетами")
            c.setFillColor(SURFACE)
            c.roundRect(card_x, y - card_h, card_w, card_h, 8, stroke=0, fill=1)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.35)
            c.roundRect(card_x, y - card_h, card_w, card_h, 8, stroke=1, fill=0)
            c.setFillColor(TEXT)
            _set_font(c, True, 12)
            text_y = y - 14
            for line in title_lines:
                c.drawString(card_x + 16, text_y, line)
                text_y -= 15
            c.setFillColor(TEXT_DIM)
            _set_font(c, False, 11)
            c.drawRightString(card_x + card_w - 14, y - 14, f"орб {orb:.1f}°")
            _set_font(c, False, 11)
            text_y -= 3
            for line in desc_lines:
                c.drawString(card_x + 16, text_y, line)
                text_y -= 13
            y -= card_h + 9
        y -= 9
    finish_page()

    # Reading.
    final_reading = str(reading or "").strip()
    if not final_reading:
        final_reading = (
            f"Ваша карта соединяет солнечный знак {_sign_ru(sun_sign)}, лунный знак {_sign_ru(moon_sign)}"
            f"{' и асцендент ' + _sign_ru(asc_sign) if asc_sign else ''}. Солнце показывает главный "
            "вектор личности, Луна описывает эмоциональные потребности, а дома показывают сферы, "
            "где качества карты раскрываются заметнее всего. Аспекты связывают разные части характера: "
            "одни дают талант и естественный поток, другие требуют взросления, честности и настройки поведения. "
            "Читайте отчёт как карту внимания: он не фиксирует судьбу, а помогает увидеть сильные стороны, "
            "зоны роста и темы, с которыми стоит обращаться бережно и осознанно."
        )
    y = title_page("Персональная интерпретация", "Написано специально для вас")
    c.setFillColor(GOLD_DIM)
    _set_font(c, False, 10)
    quote_lines = _lines_for_width(c, "«Каждый рисунок звезд раскрывается только через того, кто его носит»", w - 116, bold=False, size=10, max_lines=2)
    for quote_line in quote_lines:
        c.drawString(58, y, quote_line)
        y -= 11
    y -= 18
    c.setFillColor(TEXT)
    _set_font(c, False, 10)
    for raw_line in final_reading.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("**") and line.endswith("**"):
            header_lines = _lines_for_width(c, "✦ " + line.strip("* "), w - 116, bold=True, size=12, max_lines=2)
            header_h = 16 * len(header_lines) + 8
            if y - header_h < 64:
                finish_page()
                y = title_page("Персональная интерпретация", "Продолжение")
            c.setFillColor(GOLD)
            _set_font(c, True, 12)
            for header_line in header_lines:
                c.drawString(58, y, header_line)
                y -= 16
            y -= 8
            c.setFillColor(TEXT)
            _set_font(c, False, 10)
            continue
        paragraph = _limit_words(line, 220)
        paragraph_lines = _lines_for_width(c, paragraph, w - 116, bold=False, size=11.4)
        block_h = 17 * len(paragraph_lines) + 20
        if y - block_h < 64:
            finish_page()
            y = title_page("Персональная интерпретация", "Продолжение")
        c.setFillColor(TEXT)
        _set_font(c, False, 11.4)
        text_y = y
        for wrapped_line in paragraph_lines:
            c.drawString(58, text_y, wrapped_line)
            text_y -= 17
        y -= block_h
    finish_page()

    # Glossary.
    y = title_page("✦ Этот отчёт создан для вашего понимания", "личного космического рисунка")
    c.setFillColor(GOLD)
    _set_font(c, True, 16)
    c.drawString(48, y, "Краткий справочник")
    y -= 42
    for term, definition in GLOSSARY:
        c.setFillColor(TEXT)
        _set_font(c, True, 12.5)
        c.drawString(58, y, term)
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 11)
        y = _draw_wrapped_static(c, definition, 220, y, 38, 14, 3)
        y -= 24
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 10)
    c.drawCentredString(w / 2, 58, f"ASTRO TMA · СОЗДАНО {datetime.now().strftime('%d.%m.%Y')}")
    finish_page()
    c.save()
    return buf.getvalue()
