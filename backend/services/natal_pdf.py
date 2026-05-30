"""Generate a complete natal chart PDF report using ReportLab."""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
_FONT_REGISTERED = False
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

GOLD = HexColor("#d4b254")
GOLD_DIM = HexColor("#8a7a3a")
TEXT = HexColor("#f0ecf8")
TEXT_DIM = HexColor("#b6afca")
BG = HexColor("#07060f")
SURFACE = HexColor("#0e0b20")

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


def _register_fonts() -> None:
    """Register a Cyrillic-capable font when available, with safe built-in fallback."""
    global _FONT_REGISTERED, FONT, FONT_BOLD
    if _FONT_REGISTERED:
        return

    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/DejaVuSans.ttf",
        os.path.join(_FONT_DIR, "DejaVuSans.ttf"),
    ]
    for regular_path in regular_candidates:
        if not os.path.exists(regular_path):
            continue
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", regular_path))
            bold_path = regular_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
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
    key = _key(sign)
    return SIGN_RU.get(key, str(sign or ""))


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


def _set_font(c: canvas.Canvas, bold: bool, size: int) -> None:
    c.setFont(FONT_BOLD if bold else FONT, size)


def _draw_footer(c: canvas.Canvas, w: float) -> None:
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 8)
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
                _set_font(c, False, 10)
        else:
            line = test
    if line:
        c.drawString(x, y, line)
        y -= line_h
    return y


def _draw_title(c: canvas.Canvas, title: str, w: float, h: float, subtitle: str | None = None) -> float:
    _new_page(c, w, h)
    c.setFillColor(GOLD)
    _set_font(c, True, 20)
    c.drawString(40, h - 52, title)
    y = h - 82
    if subtitle:
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 10)
        y = _wrap_paragraph(c, subtitle, 40, y, 95, 14, 58, w, h)
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
    sign = _sign_ru(planet.get("sign_ru") or planet.get("sign"))
    house = planet.get("house") or "?"
    retro = " Ретроградность делает проявление более внутренним и требует времени на осмысление." if planet.get("retrograde") else ""
    return (
        f"{ru} в знаке {sign} показывает, как эта часть личности проявляется в вашем "
        f"характере и повседневных выборах. Положение в {house}-м доме связывает тему "
        f"планеты с конкретной сферой жизни, где она становится особенно заметной. "
        f"Обращайте внимание на ситуации, в которых качества {ru.lower()} требуют "
        f"осознанности, зрелости и бережного отношения к себе.{retro}"
    )


def _house_fallback(house: dict[str, Any]) -> str:
    num = int(house.get("number") or 0)
    sign = _sign_ru(house.get("sign_ru") or house.get("sign"))
    topic = HOUSE_TOPICS.get(num, "важную сферу жизненного опыта")
    return (
        f"{num}-й дом описывает {topic}. Знак {sign} на куспиде показывает, в каком "
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
        _set_font(c, True, 12)
        c.drawString(40, y, header)
        y -= 18
        c.setFillColor(TEXT)
        _set_font(c, False, 10)
        y = _wrap_paragraph(c, paragraph, 40, y, 95, 14, 58, w, h)
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

    # Cover and contents.
    _new_page(c, w, h)
    c.setFillColor(GOLD)
    _set_font(c, True, 28)
    c.drawCentredString(w / 2, h - 165, "НАТАЛЬНАЯ КАРТА")
    c.setFillColor(TEXT)
    _set_font(c, False, 14)
    c.drawCentredString(w / 2, h - 200, "Полный персональный отчёт")
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 11)
    c.drawCentredString(w / 2, h - 248, user_name or "Пользователь")
    c.drawCentredString(w / 2, h - 266, f"{birth_date or 'Дата не указана'}  {birth_time or ''}".strip())
    c.drawCentredString(w / 2, h - 284, birth_city or "Город не указан")

    c.setFillColor(GOLD)
    _set_font(c, True, 15)
    signs = [f"☉ {_sign_ru(sun_sign)}", f"☽ {_sign_ru(moon_sign)}"]
    if asc_sign:
        signs.append(f"AC {_sign_ru(asc_sign)}")
    c.drawCentredString(w / 2, h - 345, " · ".join(filter(None, signs)))

    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 10)
    contents = [
        "В отчёте: данные рождения и ключевые точки карты",
        "Баланс стихий и общий энергетический профиль",
        "Все планеты в знаках",
        "Все 12 домов гороскопа",
        "Все найденные аспекты между планетами",
        "Подробные описания и персональная интерпретация",
    ]
    y = h - 430
    for item in contents:
        c.drawString(118, y, f"• {item}")
        y -= 22
    _draw_footer(c, w)
    c.showPage()

    # Birth details and elements.
    y = _draw_title(c, "Ключевые данные карты", w, h, "Краткая навигация по основным точкам натальной карты.")
    rows = [
        ("Имя", user_name or "—"),
        ("Дата рождения", birth_date or "—"),
        ("Время рождения", birth_time or "не указано"),
        ("Город рождения", birth_city or "—"),
        ("Солнце", _sign_ru(sun_sign)),
        ("Луна", _sign_ru(moon_sign)),
        ("Асцендент", _sign_ru(asc_sign) if asc_sign else "не рассчитан"),
    ]
    c.setFillColor(SURFACE)
    c.roundRect(40, y - 170, w - 80, 180, 10, fill=1, stroke=0)
    y -= 24
    for label, value in rows:
        c.setFillColor(GOLD_DIM)
        _set_font(c, True, 10)
        c.drawString(62, y, label)
        c.setFillColor(TEXT)
        _set_font(c, False, 10)
        c.drawString(190, y, value)
        y -= 21

    y -= 32
    c.setFillColor(GOLD)
    _set_font(c, True, 16)
    c.drawString(40, y, "Баланс стихий")
    y -= 28
    total_planets = max(len(planets), 1)
    for element, count in _element_counts(planets).items():
        label = ELEMENTS[element][0]
        c.setFillColor(TEXT)
        _set_font(c, True, 11)
        c.drawString(58, y, label)
        c.setFillColor(TEXT_DIM)
        _set_font(c, False, 10)
        c.drawString(190, y, f"{count} из {total_planets} планет")
        y -= 20
    _draw_footer(c, w)
    c.showPage()

    # Planet table.
    y = _draw_title(c, "Планеты в знаках", w, h, "Таблица показывает знаки, градусы и дома основных планет вашей карты.")
    for name in PLANET_ORDER:
        planet = planets.get(name)
        if not planet:
            continue
        y = _ensure_space(c, y, 28, w, h)
        sign = _key(planet.get("sign"))
        sign_degree = planet.get("sign_degree", planet.get("degree", 0))
        retro = " ℞" if planet.get("retrograde") else ""
        c.setFillColor(GOLD)
        _set_font(c, True, 11)
        c.drawString(40, y, f"{PLANET_SYMBOLS[name]} {PLANET_RU[name]}")
        c.setFillColor(TEXT)
        _set_font(c, False, 10)
        c.drawString(185, y, f"{SIGN_SYMBOLS.get(sign, '')} {_sign_ru(sign)} {_deg_str(sign_degree)}{retro}")
        c.drawString(390, y, f"Дом {planet.get('house') or '—'}")
        y -= 22
    _draw_footer(c, w)
    c.showPage()

    planet_desc = (descriptions or {}).get("planets") or {}
    planet_items: list[tuple[str, str]] = []
    for name in PLANET_ORDER:
        planet = planets.get(name)
        if not planet:
            continue
        sign = _key(planet.get("sign"))
        header = f"{PLANET_SYMBOLS[name]} {PLANET_RU[name]} в {_sign_ru(sign)}"
        planet_items.append((header, _description(planet_desc.get(name), _planet_fallback(name, planet))))
    if planet_items:
        _render_items_section(
            c,
            w,
            h,
            "Планеты в знаках — подробные описания",
            "Каждая планета описывает отдельную психологическую функцию, а знак показывает стиль её проявления.",
            planet_items,
        )

    # Houses.
    y = _draw_title(c, "Дома гороскопа", w, h, "12 домов показывают жизненные сферы, где раскрываются темы карты.")
    axis_labels = {1: "Асцендент", 4: "IC", 7: "Десцендент", 10: "MC"}
    for house in houses:
        num = int(house.get("number") or 0)
        if not num:
            continue
        y = _ensure_space(c, y, 28, w, h)
        sign = _key(house.get("sign"))
        c.setFillColor(GOLD if num in axis_labels else TEXT_DIM)
        _set_font(c, bool(num in axis_labels), 10)
        c.drawString(40, y, f"Дом {num}")
        c.setFillColor(TEXT)
        _set_font(c, False, 10)
        c.drawString(125, y, f"{SIGN_SYMBOLS.get(sign, '')} {_sign_ru(sign)}")
        c.drawString(260, y, _deg_str(house.get("degree"), within_sign=False))
        if num in axis_labels:
            c.setFillColor(GOLD_DIM)
            c.drawString(340, y, f"({axis_labels[num]})")
        y -= 21
    _draw_footer(c, w)
    c.showPage()

    house_desc = (descriptions or {}).get("houses") or {}
    house_items: list[tuple[str, str]] = []
    for house in houses:
        num = int(house.get("number") or 0)
        if not num:
            continue
        sign = _key(house.get("sign"))
        house_items.append((
            f"Дом {num} — {_sign_ru(sign)}",
            _description(house_desc.get(str(num)), _house_fallback(house)),
        ))
    if house_items:
        _render_items_section(
            c,
            w,
            h,
            "Дома — подробные описания",
            "Этот раздел раскрывает, как знаки на куспидах окрашивают разные сферы жизни.",
            house_items,
        )

    # Aspects.
    y = _draw_title(c, "Аспекты между планетами", w, h, "Аспекты показывают связи, напряжения и таланты между частями карты.")
    for aspect_type in ASPECT_ORDER:
        group = [a for a in aspects if _aspect_key(a.get("aspect")) == aspect_type]
        if not group:
            continue
        y = _ensure_space(c, y, 48, w, h)
        c.setFillColor(GOLD)
        _set_font(c, True, 12)
        c.drawString(40, y, f"{ASPECT_SYMBOLS.get(aspect_type, '')} {ASPECT_RU[aspect_type]}")
        y -= 19
        for aspect in group:
            y = _ensure_space(c, y, 22, w, h)
            p1_key = _planet_key(aspect.get("p1"))
            p2_key = _planet_key(aspect.get("p2"))
            orb = float(aspect.get("orb") or 0)
            c.setFillColor(TEXT)
            _set_font(c, False, 10)
            c.drawString(
                60,
                y,
                f"{PLANET_SYMBOLS.get(p1_key, '')} {PLANET_RU.get(p1_key, aspect.get('p1', ''))}  "
                f"{ASPECT_SYMBOLS.get(aspect_type, '')}  "
                f"{PLANET_SYMBOLS.get(p2_key, '')} {PLANET_RU.get(p2_key, aspect.get('p2', ''))}",
            )
            c.setFillColor(TEXT_DIM)
            c.drawString(388, y, f"орб {orb:.1f}°")
            y -= 16
        y -= 8
    _draw_footer(c, w)
    c.showPage()

    aspect_desc = _aspect_description_map(descriptions)
    aspect_items: list[tuple[str, str]] = []
    for aspect in aspects:
        p1_key = _planet_key(aspect.get("p1"))
        p2_key = _planet_key(aspect.get("p2"))
        aspect_type = _aspect_key(aspect.get("aspect"))
        if not p1_key or not p2_key or not aspect_type:
            continue
        header = (
            f"{PLANET_RU.get(p1_key, aspect.get('p1', ''))} "
            f"{ASPECT_SYMBOLS.get(aspect_type, '')} "
            f"{PLANET_RU.get(p2_key, aspect.get('p2', ''))} — "
            f"{ASPECT_RU.get(aspect_type, aspect_type)}"
        )
        aspect_items.append((
            header,
            _description(aspect_desc.get((p1_key, p2_key, aspect_type)), _aspect_fallback(aspect)),
        ))
    if aspect_items:
        _render_items_section(
            c,
            w,
            h,
            "Аспекты — подробные описания",
            "Здесь собраны трактовки всех аспектов, найденных в натальной карте.",
            aspect_items,
        )

    final_reading = str(reading or "").strip()
    if not final_reading:
        final_reading = (
            f"Ваша карта соединяет солнечный знак {_sign_ru(sun_sign)}, лунный знак "
            f"{_sign_ru(moon_sign)}"
            f"{' и асцендент ' + _sign_ru(asc_sign) if asc_sign else ''}. "
            "Солнце показывает главный вектор личности и то, где важно проявлять волю. "
            "Луна описывает эмоциональные потребности, привычные реакции и способ "
            "восстанавливать внутренний баланс. Дома показывают, в каких сферах жизни "
            "эти качества раскрываются заметнее всего, а аспекты объясняют внутренние "
            "связи между разными частями характера. Читайте отчёт как карту внимания: "
            "он не фиксирует судьбу, а помогает увидеть сильные стороны, зоны роста и "
            "темы, с которыми стоит обращаться бережно и осознанно."
        )

    if final_reading:
        y = _draw_title(c, "Персональная интерпретация", w, h, "Итоговое чтение карты в цельном тексте.")
        c.setFillColor(TEXT)
        _set_font(c, False, 10)
        for raw_line in final_reading.split("\n"):
            line = raw_line.strip()
            if not line:
                y -= 10
                continue
            if line.startswith("**") and line.endswith("**"):
                y = _ensure_space(c, y, 28, w, h)
                c.setFillColor(GOLD)
                _set_font(c, True, 11)
                c.drawString(40, y, line.strip("* "))
                y -= 18
                c.setFillColor(TEXT)
                _set_font(c, False, 10)
                continue
            y = _wrap_paragraph(c, line, 40, y, 95, 14, 58, w, h)
        _draw_footer(c, w)
        c.showPage()

    _new_page(c, w, h)
    c.setFillColor(GOLD)
    _set_font(c, True, 18)
    c.drawCentredString(w / 2, h / 2 + 40, "Спасибо")
    c.setFillColor(TEXT_DIM)
    _set_font(c, False, 11)
    c.drawCentredString(w / 2, h / 2, "Этот отчёт создан для вашего понимания")
    c.drawCentredString(w / 2, h / 2 - 16, "личного космического рисунка.")
    _draw_footer(c, w)

    c.showPage()
    c.save()
    return buf.getvalue()
