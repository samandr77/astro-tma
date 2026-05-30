"""Tests for natal PDF generation and temporary download links."""

from types import SimpleNamespace

import pytest
from fastapi.responses import Response

from services import natal_pdf
from services.astro import natal_descriptions
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


def test_planet_description_prompt_prioritises_sign_over_house():
    prompt = natal_descriptions._planet_one_prompt(
        "sun",
        {"sign": "Capricorn", "sign_ru": "Козерог", "house": 10, "retrograde": False},
    )

    assert "Планеты в знаках" in prompt
    assert "центр разбора — связка планета + знак" in prompt
    assert "full" in prompt
    assert "6-9 предложений" not in prompt


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
    assert descriptions["_version"] == natal.NATAL_DESCRIPTIONS_VERSION
    assert chart.chart_data["descriptions"] == descriptions
    assert db.committed is True


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
async def test_send_natal_pdf_to_chat_uploads_pdf_document(monkeypatch):
    from api.routes import natal

    user = SimpleNamespace(id=1001, tg_first_name="Андрей")
    response = Response(content=b"%PDF-test", media_type="application/pdf")
    captured = {}

    class FakeHttpResponse:
        def json(self):
            return {"ok": True, "result": {"message_id": 42}}

    class FakeAsyncClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data, files):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            return FakeHttpResponse()

    async def fake_build_response(_db, passed_user):
        assert passed_user is user
        return response

    monkeypatch.setattr(natal.settings, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(natal, "_build_natal_pdf_response", fake_build_response)
    monkeypatch.setattr(natal.httpx, "AsyncClient", FakeAsyncClient)

    message_id = await natal._send_natal_pdf_to_chat(object(), user)

    assert message_id == 42
    assert captured["url"] == "https://api.telegram.org/botbot-token/sendDocument"
    assert captured["data"] == {
        "chat_id": 1001,
        "caption": "Ваш полный PDF-отчёт по натальной карте",
    }
    assert captured["files"] == {
        "document": ("natal_Андрей.pdf", b"%PDF-test", "application/pdf"),
    }


@pytest.mark.asyncio
async def test_send_natal_pdf_endpoint_returns_sent_payload(monkeypatch):
    from api.routes import natal

    user = SimpleNamespace(id=1001, tg_first_name="Андрей")

    async def fake_get_user(_db, user_id):
        assert user_id == 1001
        return user

    async def fake_send(_db, passed_user):
        assert passed_user is user
        return 42

    monkeypatch.setattr(natal, "_get_pdf_user_or_error", fake_get_user)
    monkeypatch.setattr(natal, "_send_natal_pdf_to_chat", fake_send)

    payload = await natal.send_natal_pdf_to_chat(tg_user={"id": 1001}, db=object())

    assert payload == {"sent": True, "message_id": 42}


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
