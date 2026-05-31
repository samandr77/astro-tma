"""Tests for natal PDF generation and temporary download links."""

import sys
from types import SimpleNamespace

import pytest
from fastapi.responses import Response

from services import natal_pdf, natal_pdf_html
from services.astro import llm_interpreter, natal_descriptions
from services.astro.sign_cases import sign_ru
from services.natal_pdf import generate_natal_pdf


def _sample_chart():
    planets = {
        "sun": {
            "sign": "Scorpio",
            "sign_ru": "Скорпион",
            "degree": 224.1,
            "sign_degree": 14.1,
            "house": 9,
            "retrograde": False,
        },
        "moon": {
            "sign": "Aquarius",
            "sign_ru": "Водолей",
            "degree": 309.2,
            "sign_degree": 9.2,
            "house": 1,
            "retrograde": False,
        },
        "mercury": {
            "sign": "Sagittarius",
            "sign_ru": "Стрелец",
            "degree": 241.0,
            "sign_degree": 1.0,
            "house": 10,
            "retrograde": False,
        },
    }
    houses = [
        {"number": number, "sign": "Aries", "sign_ru": "Овен", "degree": number * 30.0}
        for number in range(1, 13)
    ]
    aspects = [{"p1": "Sun", "p2": "Moon", "aspect": "square", "orb": 1.2}]
    return planets, houses, aspects


def test_generate_natal_pdf_returns_pdf_with_incomplete_descriptions():
    planets, houses, aspects = _sample_chart()

    pdf = generate_natal_pdf(
        user_name="Андрей",
        birth_date="2000-10-20",
        birth_time="12:00",
        birth_city="Минск",
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        asc_sign="Aries",
        planets=planets,
        houses=houses,
        aspects=aspects,
        descriptions={
            "planets": {"sun": {"full": "Полное описание Солнца. " * 20}},
            "houses": {},
            "aspects": [],
        },
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000


def test_generate_natal_pdf_does_not_require_dejavu_bold(monkeypatch):
    planets, houses, aspects = _sample_chart()
    monkeypatch.setattr(natal_pdf.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(natal_pdf, "_FONT_REGISTERED", False)
    monkeypatch.setattr(natal_pdf, "FONT", "Helvetica")
    monkeypatch.setattr(natal_pdf, "FONT_BOLD", "Helvetica-Bold")

    pdf = generate_natal_pdf(
        user_name="Андрей",
        birth_date="2000-10-20",
        birth_time="12:00",
        birth_city="Минск",
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        asc_sign="Aries",
        planets=planets,
        houses=houses,
        aspects=aspects,
    )

    assert pdf.startswith(b"%PDF-")


def test_generate_natal_pdf_handles_long_reading_and_many_aspects():
    planets, houses, _aspects = _sample_chart()
    planets.update(
        {
            "venus": {"sign": "Cancer", "sign_ru": "Рак", "degree": 91.0, "house": 8},
            "mars": {"sign": "Libra", "sign_ru": "Весы", "degree": 183.0, "house": 11},
            "jupiter": {
                "sign": "Gemini",
                "sign_ru": "Близнецы",
                "degree": 73.0,
                "house": 7,
                "retrograde": True,
            },
            "saturn": {"sign": "Gemini", "sign_ru": "Близнецы", "degree": 77.0, "house": 7},
            "uranus": {"sign": "Aquarius", "sign_ru": "Водолей", "degree": 318.0, "house": 5},
            "neptune": {"sign": "Aquarius", "sign_ru": "Водолей", "degree": 309.0, "house": 5},
            "pluto": {"sign": "Sagittarius", "sign_ru": "Стрелец", "degree": 252.0, "house": 2},
        }
    )
    aspects = [
        {"p1": "Sun", "p2": "Venus", "aspect": "conjunction", "orb": 6.9},
        {"p1": "Sun", "p2": "Jupiter", "aspect": "trine", "orb": 6.3},
        {"p1": "Sun", "p2": "Uranus", "aspect": "trine", "orb": 0.3},
        {"p1": "Moon", "p2": "Mercury", "aspect": "trine", "orb": 1.2},
        {"p1": "Jupiter", "p2": "Uranus", "aspect": "trine", "orb": 6.0},
        {"p1": "Jupiter", "p2": "Neptune", "aspect": "trine", "orb": 7.2},
        {"p1": "Saturn", "p2": "Neptune", "aspect": "trine", "orb": 3.5},
        {"p1": "Sun", "p2": "Pluto", "aspect": "sextile", "orb": 6.5},
        {"p1": "Mercury", "p2": "Mars", "aspect": "sextile", "orb": 2.4},
        {"p1": "Venus", "p2": "Mars", "aspect": "sextile", "orb": 4.5},
        {"p1": "Uranus", "p2": "Pluto", "aspect": "sextile", "orb": 6.2},
        {"p1": "Moon", "p2": "Jupiter", "aspect": "square", "orb": 6.0},
        {"p1": "Moon", "p2": "Pluto", "aspect": "square", "orb": 0.2},
        {"p1": "Mercury", "p2": "Uranus", "aspect": "square", "orb": 4.8},
        {"p1": "Venus", "p2": "Uranus", "aspect": "square", "orb": 2.1},
        {"p1": "Mars", "p2": "Jupiter", "aspect": "square", "orb": 3.6},
        {"p1": "Mars", "p2": "Pluto", "aspect": "square", "orb": 3.8},
        {"p1": "Moon", "p2": "Mars", "aspect": "opposition", "orb": 3.6},
        {"p1": "Jupiter", "p2": "Pluto", "aspect": "opposition", "orb": 0.2},
    ]
    reading = "\n".join(
        [
            "**Ядро личности**",
            "Вы человек противоречивый, и это ваша изюминка. " * 18,
            "**Ум и общение**",
            "Меркурий показывает точность речи, наблюдательность и умение держать фокус. " * 16,
            "**Любовь и ценности**",
            "Венера описывает глубину привязанностей, осторожность и сильные чувства. " * 16,
            "**Удача и вызовы**",
            "Юпитер и Сатурн требуют дисциплины, повторного изучения и взрослой настройки. " * 18,
        ]
    )

    pdf = generate_natal_pdf(
        user_name="Andrey",
        birth_date="2000-10-10 12:00:00",
        birth_time=None,
        birth_city="Санкт-Петербург, Россия",
        sun_sign="Libra",
        moon_sign="Pisces",
        asc_sign="Scorpio",
        planets=planets,
        houses=houses,
        aspects=aspects,
        reading=reading,
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000


def test_build_natal_pdf_html_contains_reference_layout_sections():
    planets, houses, aspects = _sample_chart()

    document = natal_pdf_html.build_natal_pdf_html(
        user_name="Андрей",
        birth_date="2000-10-20",
        birth_time="12:00",
        birth_city="Минск",
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        asc_sign="Aries",
        planets=planets,
        houses=houses,
        aspects=aspects,
    )

    assert "Натальная карта" in document
    assert "Содержание" in document
    assert "Натальное колесо" in document
    assert "Баланс стихий" in document
    assert "Планеты в знаках" in document
    assert "Дома гороскопа" in document
    assert "Персональная интерпретация" in document
    assert "wheel-svg" in document
    assert 'r="36"' not in document
    assert "@page" in document


def test_build_natal_pdf_html_keeps_full_reading_text_without_empty_page():
    planets, houses, aspects = _sample_chart()
    long_paragraph = " ".join(f"слово{i}" for i in range(120)) + " ФИНАЛЬНЫЙ_МАРКЕР"
    reading = f"**Ядро личности**\n{long_paragraph}"

    document = natal_pdf_html.build_natal_pdf_html(
        user_name="Андрей",
        birth_date="2000-10-20",
        birth_time="12:00",
        birth_city="Минск",
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        asc_sign="Aries",
        planets=planets,
        houses=houses,
        aspects=aspects,
        reading=reading,
    )

    assert "ФИНАЛЬНЫЙ_МАРКЕР" in document
    assert '<div class="reading"></div>' not in document


def test_build_natal_pdf_html_adds_continuation_pages_for_long_reading():
    planets, houses, aspects = _sample_chart()
    paragraph = " ".join(f"текст{i}" for i in range(240))
    reading = "\n".join(
        [
            "**Ядро личности**",
            paragraph,
            "**Ум и общение**",
            paragraph,
            "**Любовь и ценности**",
            paragraph,
            "**Энергия и воля**",
            paragraph,
            "**Удача и вызовы**",
            paragraph,
            "**Ключевые аспекты**",
            paragraph,
            "**Совет и путь**",
            paragraph,
        ]
    )

    document = natal_pdf_html.build_natal_pdf_html(
        user_name="Андрей",
        birth_date="2000-10-20",
        birth_time="12:00",
        birth_city="Минск",
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        asc_sign="Aries",
        planets=planets,
        houses=houses,
        aspects=aspects,
        reading=reading,
    )

    total_pages = document.count('<section class="page')
    assert total_pages > 13
    assert f"{total_pages} / {total_pages}" in document


def test_natal_reading_prompt_requests_expanded_interpretation():
    planets, _houses, aspects = _sample_chart()

    prompt = llm_interpreter._build_prompt("Scorpio", "Aquarius", "Aries", planets, aspects)

    assert "1000–1400 слов" in prompt
    assert "полноценными абзацами" in prompt
    assert "2–3 абзаца" in prompt


@pytest.mark.asyncio
async def test_generate_natal_reading_uses_expanded_token_budget(monkeypatch):
    planets, _houses, aspects = _sample_chart()
    calls = {}

    class FakeMessages:
        async def create(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text="Развёрнутое чтение.")])

    class FakeAnthropic:
        def __init__(self, api_key):
            calls["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=FakeAnthropic))

    reading = await llm_interpreter.generate_natal_reading(
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        ascendant_sign="Aries",
        planets=planets,
        aspects=aspects,
        api_key="test-key",
    )

    assert reading == "Развёрнутое чтение."
    assert calls["api_key"] == "test-key"
    assert calls["max_tokens"] == 2400


def test_planet_description_prompt_prioritises_sign_over_house():
    prompt = natal_descriptions._planet_one_prompt(
        "sun",
        {"sign": "Capricorn", "sign_ru": "Козерог", "house": 10, "retrograde": False},
    )

    assert "Планеты в знаках" in prompt
    assert "центр разбора — связка планета + знак" in prompt
    assert "Солнце в Козероге" in prompt
    assert "в знаке Козерога" in prompt
    assert "140-190 слов" in prompt
    assert "отношения, работа/дела, привычки" in prompt
    assert "full" in prompt
    assert "6-9 предложений" not in prompt


def test_sign_declensions_for_common_pdf_phrases():
    assert f"Солнце в {sign_ru('scorpio', 'prep')}" == "Солнце в Скорпионе"
    assert f"Луна в {sign_ru('aquarius', 'prep')}" == "Луна в Водолее"
    assert f"Меркурий в {sign_ru('sagittarius', 'prep')}" == "Меркурий в Стрельце"
    assert f"в знаке {sign_ru('scorpio', 'gen')}" == "в знаке Скорпиона"
    assert f"в знаке {sign_ru('aries', 'gen')}" == "в знаке Овна"
    assert f"дом в {sign_ru('libra', 'prep')}" == "дом в Весах"


def test_house_description_prompt_requests_scenarios_and_declension():
    prompt = natal_descriptions._house_one_prompt(7, "Весы")

    assert "знак на куспиде — Весы" in prompt
    assert "дом в Весах" in prompt
    assert "90-130 слов" in prompt
    assert "типичные жизненные сценарии" in prompt
    assert "сильная сторона" in prompt


def test_aspect_description_prompt_requests_full_interaction():
    prompt = natal_descriptions._aspect_one_prompt("sun", "moon", "square")

    assert "Солнце — квадрат — Луна" in prompt
    assert "110-160 слов" in prompt
    assert "взаимодействуют" in prompt
    assert "отношениях/делах" in prompt
    assert "зоны роста" in prompt


def test_html_pdf_uses_full_description_before_short():
    planets, houses, aspects = _sample_chart()
    document = natal_pdf_html.build_natal_pdf_html(
        user_name="Андрей",
        birth_date="2000-10-20",
        birth_time="12:00",
        birth_city="Минск",
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        asc_sign="Aries",
        planets=planets,
        houses=houses,
        aspects=aspects,
        descriptions={
            "planets": {
                "sun": {
                    "short": "КОРОТКИЙ_ТЕКСТ",
                    "full": "ПОЛНЫЙ_ТЕКСТ для проверки приоритета.",
                }
            },
            "houses": {},
            "aspects": [],
        },
    )

    assert "ПОЛНЫЙ_ТЕКСТ" in document
    assert "КОРОТКИЙ_ТЕКСТ" not in document


@pytest.mark.asyncio
async def test_get_or_generate_descriptions_regenerates_stale_cached_text(monkeypatch):
    from api.routes import natal

    chart = SimpleNamespace(
        chart_data={
            "planets": {"sun": {"sign": "Capricorn", "house": 10}},
            "houses": [],
            "aspects": [],
            "descriptions": {"planets": {"sun": {"full": "Старый короткий текст."}}},
        }
    )
    user = SimpleNamespace(id=1001, natal_chart=chart)
    db = SimpleNamespace(committed=False)

    async def fake_commit():
        db.committed = True

    async def fake_generate_natal_descriptions(**_kwargs):
        return {"planets": {"sun": {"full": "Новый полный справочный текст."}}, "houses": {}, "aspects": []}

    db.commit = fake_commit
    monkeypatch.setattr(natal.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(natal, "generate_natal_descriptions", fake_generate_natal_descriptions)

    descriptions = await natal._get_or_generate_descriptions(db, user)

    assert descriptions["planets"]["sun"]["full"] == "Новый полный справочный текст."
    assert descriptions["_version"] == 3
    assert descriptions["_version"] == natal.NATAL_DESCRIPTIONS_VERSION
    assert chart.chart_data["descriptions"] == descriptions
    assert db.committed is True


@pytest.mark.asyncio
async def test_get_natal_full_refreshes_short_cached_reading(monkeypatch):
    from api.routes import natal

    chart = SimpleNamespace(
        chart_data={
            "planets": {"sun": {"sign": "Scorpio", "house": 9}},
            "aspects": [{"p1": "Sun", "p2": "Moon", "aspect": "square", "orb": 1.2}],
        },
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        ascendant_sign="Aries",
    )
    user = SimpleNamespace(id=1001, natal_chart=chart)
    cached = {"reading": "**Ядро личности**\nКоротко.", "planets": chart.chart_data["planets"]}
    refreshed_text = "\n".join(
        [
            "**Ядро личности**",
            "слово " * 140,
            "**Ум и общение**",
            "слово " * 140,
            "**Любовь и ценности**",
            "слово " * 140,
            "**Энергия и воля**",
            "слово " * 140,
            "**Удача и вызовы**",
            "слово " * 140,
        ]
    )
    calls = {}

    async def fake_get_by_id(_db, user_id):
        assert user_id == 1001
        return user

    async def fake_true(_db, user_id, *_args):
        assert user_id == 1001
        return True

    async def fake_cache_get(key):
        assert key == "natal:1001"
        return cached

    async def fake_cache_set(key, value, ttl):
        calls["cache_set"] = (key, value, ttl)

    async def fake_generate_natal_reading(**kwargs):
        calls["reading_kwargs"] = kwargs
        return refreshed_text

    monkeypatch.setattr(natal.user_repo, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(natal.user_repo, "is_premium", fake_true)
    monkeypatch.setattr(natal.user_repo, "has_purchased", fake_true)
    monkeypatch.setattr(natal, "cache_get", fake_cache_get)
    monkeypatch.setattr(natal, "cache_set", fake_cache_set)
    monkeypatch.setattr(natal.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(natal, "generate_natal_reading", fake_generate_natal_reading)

    result = await natal.get_natal_full(tg_user={"id": 1001}, db=object())

    assert result["reading"] == refreshed_text
    assert result["planets"] == chart.chart_data["planets"]
    assert calls["reading_kwargs"]["aspects"] == chart.chart_data["aspects"]
    assert calls["cache_set"][0] == "natal:1001"
    assert calls["cache_set"][1]["reading"] == refreshed_text


@pytest.mark.asyncio
async def test_create_natal_pdf_link_returns_temporary_download_payload(monkeypatch):
    from api.routes import natal

    async def fake_get_user(_db, user_id):
        return SimpleNamespace(id=user_id, tg_first_name="Андрей")

    calls = {}

    async def fake_cache_set(key, value, ttl):
        calls["key"] = key
        calls["value"] = value
        calls["ttl"] = ttl

    monkeypatch.setattr(natal, "_get_pdf_user_or_error", fake_get_user)
    monkeypatch.setattr(natal, "cache_set", fake_cache_set)
    monkeypatch.setattr(natal, "token_urlsafe", lambda _size: "token-123")

    payload = await natal.create_natal_pdf_link(tg_user={"id": 1001}, db=object())

    assert payload == {
        "download_url": "/natal/pdf-download/token-123",
        "filename": "natal_Андрей.pdf",
        "expires_in": 300,
    }
    assert calls == {
        "key": "natal:pdf-download:token-123",
        "value": {"user_id": 1001},
        "ttl": 300,
    }


@pytest.mark.asyncio
async def test_natal_pdf_token_download_does_not_require_telegram_auth(monkeypatch):
    from api.routes import natal

    async def fake_cache_get(key):
        assert key == "natal:pdf-download:token-123"
        return {"user_id": 1001}

    async def fake_get_user(_db, user_id):
        assert user_id == 1001
        return SimpleNamespace(id=user_id)

    async def fake_build_response(_db, user):
        assert user.id == 1001
        return Response(content=b"%PDF-test", media_type="application/pdf")

    monkeypatch.setattr(natal, "cache_get", fake_cache_get)
    monkeypatch.setattr(natal, "_get_pdf_user_or_error", fake_get_user)
    monkeypatch.setattr(natal, "_build_natal_pdf_response", fake_build_response)

    response = await natal.get_natal_pdf_by_token("token-123", db=object())

    assert response.body == b"%PDF-test"
    assert response.media_type == "application/pdf"


@pytest.mark.asyncio
async def test_send_natal_pdf_to_telegram_generates_and_sends_document(monkeypatch):
    from api.routes import natal

    user = SimpleNamespace(id=1001, tg_first_name="Андрей")
    calls = {}

    async def fake_get_user(_db, user_id):
        assert user_id == 1001
        return user

    async def fake_build_pdf(_db, pdf_user):
        assert pdf_user is user
        calls["generated"] = True
        return b"%PDF-test"

    async def fake_send(pdf_user, pdf_bytes):
        assert pdf_user is user
        calls["sent_bytes"] = pdf_bytes

    monkeypatch.setattr(natal, "_get_pdf_user_or_error", fake_get_user)
    monkeypatch.setattr(natal, "_build_natal_pdf_bytes", fake_build_pdf)
    monkeypatch.setattr(natal, "_send_natal_pdf_document", fake_send)

    payload = await natal.send_natal_pdf_to_telegram(tg_user={"id": 1001}, db=object())

    assert payload == {"status": "sent", "filename": "natal_Андрей.pdf"}
    assert calls == {"generated": True, "sent_bytes": b"%PDF-test"}


@pytest.mark.asyncio
async def test_build_natal_pdf_response_does_not_block_on_llm(monkeypatch):
    from api.routes import natal
    from services import natal_pdf, natal_pdf_html

    chart = SimpleNamespace(
        chart_data={
            "planets": {"sun": {"sign": "scorpio"}},
            "houses": [],
            "aspects": [],
        },
        sun_sign="scorpio",
        moon_sign="aries",
        ascendant_sign="capricorn",
    )
    user = SimpleNamespace(
        id=1001,
        tg_first_name="Андрей",
        birth_date=None,
        birth_time_known=False,
        birth_city="Минск",
        natal_chart=chart,
    )
    calls = {}

    async def fail_descriptions(*_args, **_kwargs):
        raise AssertionError("download must not generate descriptions")

    async def fail_reading(*_args, **_kwargs):
        raise AssertionError("download must not generate reading")

    async def fake_cache_get(key):
        calls["cache_key"] = key
        return None

    def fake_generate_natal_pdf(**kwargs):
        calls["pdf_kwargs"] = kwargs
        return b"%PDF-fast"

    async def fake_generate_natal_pdf_html(**_kwargs):
        raise RuntimeError("chromium unavailable")

    monkeypatch.setattr(natal, "_get_or_generate_descriptions", fail_descriptions)
    monkeypatch.setattr(natal, "_get_or_generate_pdf_reading", fail_reading)
    monkeypatch.setattr(natal, "cache_get", fake_cache_get)
    monkeypatch.setattr(natal_pdf_html, "generate_natal_pdf_html", fake_generate_natal_pdf_html)
    monkeypatch.setattr(natal_pdf, "generate_natal_pdf", fake_generate_natal_pdf)

    response = await natal._build_natal_pdf_response(db=object(), user=user)

    assert response.body == b"%PDF-fast"
    assert calls["cache_key"] == "natal:1001"
    assert calls["pdf_kwargs"]["descriptions"] == natal._empty_descriptions()
    assert calls["pdf_kwargs"]["reading"] is None


@pytest.mark.asyncio
async def test_pdf_reading_is_generated_when_full_chart_cache_is_cold(monkeypatch):
    from api.routes import natal

    calls = {}
    chart = SimpleNamespace(
        sun_sign="Scorpio",
        moon_sign="Aquarius",
        ascendant_sign="Aries",
    )
    planets = {"sun": {"sign": "Scorpio"}}
    aspects = [{"p1": "Sun", "p2": "Moon", "aspect": "square", "orb": 1.2}]
    user = SimpleNamespace(id=1001)

    async def fake_cache_get(key):
        calls["cache_get_key"] = key
        return None

    async def fake_cache_set(key, value, ttl):
        calls["cache_set"] = (key, value, ttl)

    async def fake_reading(**kwargs):
        calls["reading_kwargs"] = kwargs
        return "Полное итоговое чтение карты."

    monkeypatch.setattr(natal, "cache_get", fake_cache_get)
    monkeypatch.setattr(natal, "cache_set", fake_cache_set)
    monkeypatch.setattr(natal.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(natal, "generate_natal_reading", fake_reading)

    reading = await natal._get_or_generate_pdf_reading(user, chart, planets, aspects)

    assert reading == "Полное итоговое чтение карты."
    assert calls["reading_kwargs"]["aspects"] == aspects
    assert calls["cache_set"][0] == "natal:1001"
    assert calls["cache_set"][1]["reading"] == "Полное итоговое чтение карты."
