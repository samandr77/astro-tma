"""
Destiny Matrix calculator — pure math, no I/O, no LLM.

Источник методики: книга «Матрица судьбы от А до Я» (Н. Бастиков, метод Л. Ладини).
Традиция арканов: Marseille (8=Справедливость, 11=Сила, 22=Шут/Свобода).

ВАЛИДАЦИЯ: формулы проверены на эталонном примере из книги (23.01.1987)
плюс на трёх независимых публичных источниках (Халва 10.04.1988,
Dzen 09.01.2001, ИнфоХит 22.11.1983). Полный тест-сьют — в
tests/test_calculator.py (28 тестов).

Используются английские code-ключи (`day`, `month`, `top_left`, …) —
display labels на русском живут в UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

# ── Свёртка ─────────────────────────────────────────────────────────────────

def reduce(n: int) -> int:
    """Свёртка к диапазону арканов 1..22 сложением цифр.
    Примеры: 25→7, 26→8, 23→5, 30→3. Месяцы (1..12) и суммы ≤22 не сворачиваются."""
    while n > 22:
        n = sum(int(d) for d in str(n))
    return n


def reduce1(n: int) -> int:
    """Ведическая свёртка до 1..9 — используется для расчёта варн."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n


def ray_dots(corner: int, center: int) -> list[int]:
    """3 внутренние точки на луче «угол → центр» по методу Ладини.

    Рекурсивное правило середины (fillLine, depth=2) развёрнуто:
        mid         = corner + center
        near_corner = corner + mid
        near_center = mid + center
    Возвращает [near_corner, mid, near_center] — порядок от угла к центру.
    Сам угол в массив не входит (он рисуется отдельным большим узлом)."""
    mid = reduce(corner + center)
    near_corner = reduce(corner + mid)
    near_center = reduce(mid + center)
    return [near_corner, mid, near_center]


# ── Авторские названия арканов из книги ────────────────────────────────────

ARCANA_NAMES: dict[int, str] = {
    1: "Маг", 2: "Единство", 3: "Императрица", 4: "Император",
    5: "Учитель", 6: "Любовь", 7: "Воин",
    8: "Справедливость", 9: "Мудрец", 10: "Фортуна",
    11: "Сила", 12: "Новое видение", 13: "Трансформация",
    14: "Искусство", 15: "Проявление", 16: "Духовное преображение",
    17: "Звезда", 18: "Магия", 19: "Солнце",
    20: "Ясно знание", 21: "Мир", 22: "Уровневая свобода",
}


# ── Касты для расчёта варны (по числам кармы 1..9) ──────────────────────────

VARNA = {
    1: "Кшатрий", 9: "Кшатрий",
    3: "Брахман", 6: "Брахман",
    2: "Вайшью", 5: "Вайшью",
    4: "Шудра", 7: "Шудра", 8: "Шудра",
}


# ── Структуры данных ────────────────────────────────────────────────────────

@dataclass
class Channel:
    """Канал-«ключ» из трёх энергий: начало, середина, итог."""
    a: int
    b: int
    c: int

    def as_list(self) -> list[int]:
        return [self.a, self.b, self.c]


@dataclass
class ChakraSet:
    """7 чакр на одной из линий (Небо или Земля)."""
    sahasrara: int
    adjna: int
    vishuddha: int
    anahata: int
    manipura: int
    svadhisthana: int
    muladhara: int


@dataclass
class DestinyMatrix:
    # §1 Личностный (диагональный) ромб
    day: int
    month: int
    year: int
    bottom: int
    center: int

    # §2 Родовой (прямой) квадрат
    anc_top_left: int
    anc_top_right: int
    anc_bottom_right: int
    anc_bottom_left: int
    # Центр родового квадрата (4 угла + reduce) — спека Ладини
    center_lineage: int
    # Целостный центр силы — слияние личного и родового
    center_holistic: int

    # §3 Линии и предназначения (4 базовых)
    sky: int
    earth: int
    line_father: int
    line_mother: int
    purpose_personal: int      # 3-е по спеке: holisticPersonal
    purpose_social: int        # 6-е по спеке: holisticLineage
    purpose_spiritual: int     # 7-е по спеке: personalDivine
    purpose_planetary: int     # 8-е по спеке: divineMission

    # §4 Каналы (3 энергии каждый)
    karmic_tail: Channel
    talents: Channel
    relationships: Channel
    finance: Channel
    material_karma: Channel
    parental: Channel
    ancestral_father: Channel   # таланты по линии отца (ATL)
    ancestral_father2: Channel  # карма по линии отца (ABR)
    ancestral_mother: Channel   # таланты по линии матери (ATR)
    ancestral_mother2: Channel  # карма по линии матери (ABL)

    # §5 Чакры по двум линиям + точки денег/партнёра
    chakras_sky: ChakraSet
    chakras_earth: ChakraSet
    money_entry: int     # Свадхистана по Земле = reduce(center + year)
    partner_entry: int   # Свадхистана по Небу = reduce(center + bottom)

    # Дополнительные точки
    cross_point: int
    material_karma_point: int


# ── Расчёт ──────────────────────────────────────────────────────────────────

def calculate(birth: date) -> DestinyMatrix:
    """Полный расчёт Матрицы Судьбы по дате рождения. Чистая математика,
    детерминированная: одна дата → одна матрица."""

    # §1 Личностный квадрат (диагональный ромб)
    D = reduce(birth.day)
    M = reduce(birth.month)
    Y = reduce(sum(int(c) for c in str(birth.year)))
    B = reduce(D + M + Y)
    C = reduce(D + M + Y + B)

    # §2 Родовой квадрат (прямой)
    atl = reduce(D + M)
    atr = reduce(M + Y)
    abr = reduce(Y + B)
    abl = reduce(B + D)

    # §3 Линии и предназначения
    sky = reduce(M + B)
    earth = reduce(D + Y)
    line_father = reduce(atl + abr)
    line_mother = reduce(atr + abl)
    lp = reduce(sky + earth)            # личное (до 40 лет)
    sp = reduce(line_father + line_mother)  # социальное (40-60)
    dp = reduce(lp + sp)                # духовное (после 60)
    pp = reduce(sp + dp)                # планетарное (миссия)

    # §4.1 Кармический хвост (приём «вершина + C, затем + вершина»)
    kt = Channel(B, reduce(B + C), reduce(B + reduce(B + C)))

    # §4.2 Зона талантов
    tal = Channel(M, reduce(M + C), reduce(M + reduce(M + C)))

    # §4.3 Линия благополучия: отношения + финансы (пересекаются)
    mk_point = reduce(Y + C)                 # точка материальной кармы (стык)
    cross = reduce(kt.b + mk_point)
    rel_center = reduce(kt.b + cross)
    fin_center = reduce(mk_point + cross)
    relationships = Channel(kt.b, rel_center, cross)
    finance = Channel(mk_point, fin_center, cross)

    # §4.4 Материальная карма
    mk_center = reduce(Y + mk_point)
    material_karma = Channel(Y, mk_center, mk_point)

    # §4.5 Детско-родительский (на линии Земли)
    parental = Channel(D, reduce(D + C), reduce(D + reduce(D + C)))

    # §4.6 Родовые каналы (приём «вершина + C, затем + вершина»)
    af1 = reduce(atl + C); af2 = reduce(atl + af1)
    af3 = reduce(abr + C); af4 = reduce(abr + af3)
    am1 = reduce(atr + C); am2 = reduce(atr + am1)
    am3 = reduce(abl + C); am4 = reduce(abl + am3)

    # §5 Чакры (Небо: M-C-B; Земля: D-C-Y)
    # Свадхистана = ключевая точка пути по линии: партнёр (Небо), деньги (Земля)
    sky_vishuddha = reduce(M + C)
    sky_anahata = reduce(sky_vishuddha + C)
    sky_svadhisthana = reduce(C + B)
    chakras_sky = ChakraSet(
        sahasrara=M,
        adjna=reduce(M + sky_vishuddha),
        vishuddha=sky_vishuddha,
        anahata=sky_anahata,
        manipura=C,
        svadhisthana=sky_svadhisthana,
        muladhara=B,
    )
    earth_vishuddha = reduce(D + C)
    earth_anahata = reduce(earth_vishuddha + C)
    earth_svadhisthana = reduce(C + Y)
    chakras_earth = ChakraSet(
        sahasrara=D,
        adjna=reduce(D + earth_vishuddha),
        vishuddha=earth_vishuddha,
        anahata=earth_anahata,
        manipura=C,
        svadhisthana=earth_svadhisthana,
        muladhara=Y,
    )

    # §6 Центр родовой силы и целостный центр
    center_lineage = reduce(atl + atr + abr + abl)
    center_holistic = reduce(C + center_lineage)

    return DestinyMatrix(
        day=D, month=M, year=Y, bottom=B, center=C,
        anc_top_left=atl, anc_top_right=atr,
        anc_bottom_right=abr, anc_bottom_left=abl,
        center_lineage=center_lineage,
        center_holistic=center_holistic,
        sky=sky, earth=earth,
        line_father=line_father, line_mother=line_mother,
        purpose_personal=lp, purpose_social=sp,
        purpose_spiritual=dp, purpose_planetary=pp,
        karmic_tail=kt, talents=tal,
        relationships=relationships, finance=finance,
        material_karma=material_karma, parental=parental,
        ancestral_father=Channel(atl, af1, af2),
        ancestral_father2=Channel(abr, af3, af4),
        ancestral_mother=Channel(atr, am1, am2),
        ancestral_mother2=Channel(abl, am3, am4),
        chakras_sky=chakras_sky,
        chakras_earth=chakras_earth,
        money_entry=earth_svadhisthana,
        partner_entry=sky_svadhisthana,
        cross_point=cross, material_karma_point=mk_point,
    )


def calculate_varna(birth: date) -> dict:
    """Расчёт варн (каст) по дате рождения. Ведическая свёртка до 1..9.

    Правило: рождение 00:00-01:30 → берётся предыдущий день. Здесь время
    не учитываем — варну считаем от паспортной даты как есть, корректировку
    оставляем UI/пользователю.
    """
    d = reduce1(birth.day)
    m = reduce1(birth.month)
    y = reduce1(sum(int(c) for c in str(birth.year)))
    s = reduce1(d + m + y)
    result: dict[str, int] = {}
    for digit, pct in [(d, 40), (m, 10), (y, 10), (s, 40)]:
        v = VARNA.get(digit, "—")
        result[v] = result.get(v, 0) + pct
    return {
        "varnas": result,
        "expression": reduce1(birth.day + birth.month),
    }


def _chakra_dict(c: ChakraSet) -> dict[str, int]:
    return {
        "sahasrara": c.sahasrara, "adjna": c.adjna, "vishuddha": c.vishuddha,
        "anahata": c.anahata, "manipura": c.manipura,
        "svadhisthana": c.svadhisthana, "muladhara": c.muladhara,
    }


# Чакры (top→bottom) для построения «карты здоровья». Каждая чакра
# даёт ключ здоровья = reduce(energy + physics).
_CHAKRA_ORDER = (
    "sahasrara", "adjna", "vishuddha", "anahata",
    "manipura", "svadhisthana", "muladhara",
)


def _health_map(sky: ChakraSet, earth: ChakraSet) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sum_energy = 0
    sum_physics = 0
    sum_keys = 0
    for key in _CHAKRA_ORDER:
        energy = getattr(sky, key)
        physics = getattr(earth, key)
        k = reduce(energy + physics)
        rows.append({"chakra": key, "energy": energy, "physics": physics, "key": k})
        sum_energy += energy
        sum_physics += physics
        sum_keys += k
    return {
        "rows": rows,
        "system": {
            "energy": reduce(sum_energy),
            "physics": reduce(sum_physics),
            "key": reduce(sum_keys),
        },
    }


def _comfort_pair(b: int, c: int) -> list[int]:
    """Две точки «зоны комфорта» справа от центра.

    Возвращает `[comfort_a, comfort_b]`, где:
      comfort_a = reduce(2B + 2C) — ближе к центру
      comfort_b = reduce(2B + C)  — дальше (ближе к money point)

    Валидировано против эталона matritsa-sudbi.ru на 3 датах:
      15.12.2001 (B=3, C=6)  → comfort_a=18, comfort_b=12 ✓
      13.01.1988 (B=22, C=8) → comfort_a=15, comfort_b=7  ✓
      17.08.2000 (B=9, C=9)  → comfort_a=18, comfort_b=9  ✓
    Все 36 полей OctagramData сходятся 1-в-1."""
    comfort_b_val = reduce(2 * b + c)
    comfort_a_val = reduce(comfort_b_val + c)
    return [comfort_a_val, comfort_b_val]


def _half_diag(corner: int, c: int) -> list[int]:
    """Полудиагональ от центра к углу прямого квадрата (TL/TR/BR/BL).

    Возвращает `[near_center, near_corner]` — 2 точки на цветной стрелке:
      near_center = reduce(corner + C)            (= mid точки луча)
      near_corner = reduce(corner + near_center)  (= near_corner точки луча)
    Эти значения совпадают с channels[ancestral_*][0] и [1] —
    но визуально рисуются на стрелках линий рода, а не на диагональных лучах."""
    near_center = reduce(corner + c)
    near_corner = reduce(corner + near_center)
    return [near_center, near_corner]


def to_dict(m: DestinyMatrix) -> dict[str, Any]:
    """Сериализация в плоский dict для JSONB / API ответа."""
    sky = _chakra_dict(m.chakras_sky)
    earth = _chakra_dict(m.chakras_earth)

    # mid-точки лучей (одновременно — семантические лейблы)
    talent = reduce(m.month + m.center)   # = mid верхнего луча
    character = reduce(m.day + m.center)  # = mid левого луча (без явного лейбла)
    money = reduce(m.year + m.center)     # = mid правого луча («деньги»)
    love = reduce(m.bottom + m.center)    # = mid нижнего луча («любовь»)
    cross = reduce(love + money)          # = reduce((B+C) + (Y+C))
    comfort = _comfort_pair(m.bottom, m.center)
    money_diag_1 = reduce(cross + money)
    love_diag_1 = reduce(cross + love)
    # Линии рода — по 2 точки на полудиагонали, на цветных стрелках
    # (синяя = TL↔BR мужская, красная = TR↔BL женская).
    male_upper = _half_diag(m.anc_top_left, m.center)
    male_lower = _half_diag(m.anc_bottom_right, m.center)
    female_upper = _half_diag(m.anc_top_right, m.center)
    female_lower = _half_diag(m.anc_bottom_left, m.center)

    return {
        "personality": {
            "day": m.day, "month": m.month, "year": m.year,
            "bottom": m.bottom, "center": m.center,
        },
        "ancestral_square": {
            "top_left": m.anc_top_left, "top_right": m.anc_top_right,
            "bottom_right": m.anc_bottom_right, "bottom_left": m.anc_bottom_left,
        },
        "centers": {
            "personal": m.center,
            "lineage": m.center_lineage,
            "holistic": m.center_holistic,
        },
        "lines": {
            "sky": m.sky, "earth": m.earth,
            "father": m.line_father, "mother": m.line_mother,
        },
        # 4 базовых предназначения (совместимо со старой версией)
        "purposes": {
            "personal": m.purpose_personal,
            "social": m.purpose_social,
            "spiritual": m.purpose_spiritual,
            "planetary": m.purpose_planetary,
        },
        # 8 предназначений по спеке Ладини (новое)
        "purposes_full": {
            "sky_personal": m.sky,
            "earth_personal": m.earth,
            "holistic_personal": m.purpose_personal,
            "father_line": m.line_father,
            "mother_line": m.line_mother,
            "holistic_lineage": m.purpose_social,
            "personal_divine": m.purpose_spiritual,
            "divine_mission": m.purpose_planetary,
        },
        # 8 «лучевых» каналов отдают 3 точки луча [near_corner, mid, near_center].
        # 2 «cross»-канала (отношения, финансы) идут как было — пересекающиеся,
        # к лучу не привязаны.
        "channels": {
            "karmic_tail": ray_dots(m.bottom, m.center),
            "talents": ray_dots(m.month, m.center),
            "relationships": m.relationships.as_list(),
            "finance": m.finance.as_list(),
            "material_karma": ray_dots(m.year, m.center),
            "parental": ray_dots(m.day, m.center),
            "ancestral_father_talents": ray_dots(m.anc_top_left, m.center),
            "ancestral_father_karma": ray_dots(m.anc_bottom_right, m.center),
            "ancestral_mother_talents": ray_dots(m.anc_top_right, m.center),
            "ancestral_mother_karma": ray_dots(m.anc_bottom_left, m.center),
        },
        # Семантические точки внутри октаграммы. talent/character/money/love
        # дублируют channels[*][1] (mid-ы лучей), но удобно иметь явные ключи.
        # love_diag_1 = «любовная» диагональ (зеркало money_diag_1).
        "specials": {
            "talent": talent,
            "character": character,
            "money": money,
            "love": love,
            "cross": cross,
            "comfort": comfort,     # [comfort_a, comfort_b] = [2B+2C, 2B+C]
            "love_diag_1": love_diag_1,
        },
        # Денежная пунктирная диагональ от центра в сторону BR угла.
        # 3 точки: [cross+money, cross, money].
        "money_diagonal": [money_diag_1, cross, money],
        # Линии рода — 4 полудиагонали, каждая по [near_center, near_corner]:
        # мужская TL↔BR (синяя), женская TR↔BL (красная).
        "family_lines": {
            "male_upper": male_upper,
            "male_lower": male_lower,
            "female_upper": female_upper,
            "female_lower": female_lower,
        },
        "chakras": {
            "sky": sky,
            "earth": earth,
        },
        "health_map": _health_map(m.chakras_sky, m.chakras_earth),
        "entries": {
            "money": m.money_entry,
            "partner": m.partner_entry,
        },
    }


# ── Public entry point — совместим с прежним API ────────────────────────────

def calculate_matrix(birth_date: date) -> dict[str, Any]:
    """Удобная обёртка: считает матрицу + варну и возвращает плоский dict
    для хранения в JSONB. Используется из api/routes/destiny_matrix.py."""
    return {
        **to_dict(calculate(birth_date)),
        "varna": calculate_varna(birth_date),
    }
