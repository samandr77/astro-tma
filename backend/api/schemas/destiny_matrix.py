"""Pydantic schemas for the /api/destiny-matrix endpoints.

Структура соответствует MATRIX_DESTINY_SPEC.md §4.2 + §5.1 — то что
возвращает `calculator.calculate_matrix(birth_date)`.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

# ── Подблоки positions ──────────────────────────────────────────────────────

class PersonalityBlock(BaseModel):
    """§2.1 Личностный (диагональный) ромб."""
    day: int
    month: int
    year: int
    bottom: int
    center: int


class AncestralSquareBlock(BaseModel):
    """§2.2 Родовой (прямой) квадрат."""
    top_left: int
    top_right: int
    bottom_right: int
    bottom_left: int


class LinesBlock(BaseModel):
    """§2.3 Земля/Небо + мужская/женская линии рода."""
    sky: int
    earth: int
    father: int
    mother: int


class PurposesBlock(BaseModel):
    """§2.3 Предназначения: личное (<40), социальное (40-60),
    духовное (60+), планетарное (миссия)."""
    personal: int
    social: int
    spiritual: int
    planetary: int


class ChannelsBlock(BaseModel):
    """§2.4 Десять каналов по 3 энергии (start/middle/outcome)."""
    karmic_tail: list[int]
    talents: list[int]
    relationships: list[int]
    finance: list[int]
    material_karma: list[int]
    parental: list[int]
    ancestral_father_talents: list[int]
    ancestral_father_karma: list[int]
    ancestral_mother_talents: list[int]
    ancestral_mother_karma: list[int]


class VarnaBlock(BaseModel):
    """§2.5 Варна — касты по числам кармы (1..9), четыре доли."""
    varnas: dict[str, int]   # {"Брахман": 40, "Кшатрий": 40, ...}
    expression: int


class CentersBlock(BaseModel):
    """Три центра силы по методике Ладини."""
    personal: int       # центр диагонали
    lineage: int        # центр родового квадрата = reduce(tl+tr+br+bl)
    holistic: int       # reduce(personal + lineage)


class PurposesFullBlock(BaseModel):
    """8 предназначений по спеке Ладини."""
    sky_personal: int
    earth_personal: int
    holistic_personal: int
    father_line: int
    mother_line: int
    holistic_lineage: int
    personal_divine: int
    divine_mission: int


class ChakraSetBlock(BaseModel):
    sahasrara: int
    adjna: int
    vishuddha: int
    anahata: int
    manipura: int
    svadhisthana: int
    muladhara: int


class ChakrasBlock(BaseModel):
    """7 чакр × 2 линии (Небо / Земля)."""
    sky: ChakraSetBlock
    earth: ChakraSetBlock


class HealthMapRow(BaseModel):
    chakra: str
    energy: int
    physics: int
    key: int


class HealthMapSystem(BaseModel):
    energy: int
    physics: int
    key: int


class HealthMapBlock(BaseModel):
    """Карта здоровья — 7 строк × (energy, physics, key) + системный итог."""
    rows: list[HealthMapRow]
    system: HealthMapSystem


class EntriesBlock(BaseModel):
    """Денежный и партнёрский «вход» — точки на линии Земли/Неба."""
    money: int
    partner: int


class SpecialsBlock(BaseModel):
    """Семантические точки внутри октаграммы. talent/character/money/love
    дублируют mid-ы соответствующих лучей, comfort — пара точек справа
    от центра, cross — точка между центром и нижним лучом."""
    talent: int       # M+C (mid верхнего луча)
    character: int    # D+C (mid левого луча)
    money: int        # Y+C (mid правого луча)
    love: int         # B+C (mid нижнего луча)
    cross: int        # reduce(love + money)
    comfort: list[int]  # [comfort_a, comfort_b] = [2B+2C, 2B+C]
    love_diag_1: int | None = None  # reduce(cross + love); зеркало money_diag_1


class FamilyLinesBlock(BaseModel):
    """Линии рода: 4 полудиагонали, каждая по 2 точки [near_center, near_corner].

    Мужская линия — TL ↔ центр ↔ BR (синяя стрелка).
    Женская линия — TR ↔ центр ↔ BL (красная стрелка)."""
    male_upper: list[int]    # к TL углу прямого квадрата
    male_lower: list[int]    # к BR углу
    female_upper: list[int]  # к TR углу
    female_lower: list[int]  # к BL углу


class DestinyMatrixPositions(BaseModel):
    personality: PersonalityBlock
    ancestral_square: AncestralSquareBlock
    lines: LinesBlock
    purposes: PurposesBlock
    channels: ChannelsBlock
    varna: VarnaBlock
    # Новые блоки по спеке Ладини. Делаем опциональными — старые записи
    # без них (если такие случайно остались) не упадут на десериализации.
    centers: CentersBlock | None = None
    purposes_full: PurposesFullBlock | None = None
    chakras: ChakrasBlock | None = None
    health_map: HealthMapBlock | None = None
    entries: EntriesBlock | None = None
    specials: SpecialsBlock | None = None
    money_diagonal: list[int] | None = None
    family_lines: FamilyLinesBlock | None = None


# ── Ответы эндпоинтов ───────────────────────────────────────────────────────

class DestinyMatrixResponse(BaseModel):
    positions: DestinyMatrixPositions
    birth_date: date
    computed_at: datetime
    has_full_access: bool


class ArcanaResponse(BaseModel):
    """Все 9 контекстных трактовок для одного аркана — payload для
    bottom-sheet'а по тапу узла октаграммы. Клиент сам выбирает какой
    контекст показывать (по тому какой узел тапнули)."""
    arcana_num: int
    arcana_name: str
    keywords: list[str]
    contexts: dict[str, str]   # context_key → meaning_ru


class InterpretationResponse(BaseModel):
    """LLM-сгенерированный 8-секционный личный разбор. Кешируется per reading_id.

    V2: bottom-2 free, остальные 6 секций под premium-гейтом. Поле
    `locked_sections` помечает, какие ключи фронту нужно прятать под
    замок. Для премиумов это всегда пустой список."""
    reading_id: int
    sections: dict[str, str]   # who_you_are, karmic_tail, talents, purpose,
                               # relationships, finance, parental, advice
    model: str
    generated_at: datetime
    has_full_access: bool = True
    locked_sections: list[str] = []
