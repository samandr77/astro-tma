"""Unit tests for notification message formatting."""

from datetime import date

from db.models import User
from services.notifications.push import (
    DAILY_OPEN_APP_LABEL,
    build_daily_message,
    build_open_app_markup,
)


def _user() -> User:
    return User(id=1001, tg_first_name="Андрей")


def test_daily_message_hides_energy_stats():
    message = build_daily_message(
        _user(),
        sign_ru="Скорпион",
        text_ru="Сегодня лучше не спешить с выводами.",
        energy={"love": 91, "career": 72, "luck": 64},
        message_date=date(2026, 5, 16),
    )

    assert "91%" not in message
    assert "72%" not in message
    assert "64%" not in message
    assert "Любовь" not in message
    assert "Карьера" not in message
    assert "Удача" not in message


def test_daily_message_changes_by_date_even_with_same_horoscope():
    today = build_daily_message(
        _user(),
        sign_ru="Скорпион",
        text_ru="Информация не изменилась, но подача должна быть живой.",
        energy={},
        message_date=date(2026, 5, 16),
    )
    tomorrow = build_daily_message(
        _user(),
        sign_ru="Скорпион",
        text_ru="Информация не изменилась, но подача должна быть живой.",
        energy={},
        message_date=date(2026, 5, 17),
    )

    assert today != tomorrow
    assert "16 мая" in today
    assert "17 мая" in tomorrow


def test_open_app_markup_returns_webapp_button(monkeypatch):
    from core.settings import settings

    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", "https://example.com/")

    markup = build_open_app_markup("Открыть")

    assert markup is not None
    assert markup["inline_keyboard"][0][0]["text"] == "Открыть"
    assert markup["inline_keyboard"][0][0]["web_app"]["url"] == "https://example.com/"


def test_open_app_markup_default_label_invites_to_finish_reading(monkeypatch):
    from core.settings import settings

    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", "https://example.com/")

    markup = build_open_app_markup()

    # The label should match the cliff-hanger framing of the push body.
    assert DAILY_OPEN_APP_LABEL == "✦ Дочитать в приложении"
    assert markup is not None
    assert markup["inline_keyboard"][0][0]["text"] == DAILY_OPEN_APP_LABEL


def test_open_app_markup_returns_none_when_url_missing(monkeypatch):
    from core.settings import settings
    monkeypatch.setattr(settings, "TELEGRAM_WEBAPP_URL", "")

    assert build_open_app_markup() is None


def test_daily_message_ends_with_cliffhanger_ellipsis():
    """Push has to break off mid-thought so the user has a reason to tap
    "Читать далее" inside the bot."""
    long_text = (
        "В этот день Луна в Деве создаёт гармоничный секстиль с вашим "
        "управителем Плутоном, пробуждая в вас дар различения и стратегического "
        "видения — используйте эту ясность для решения давних профессиональных "
        "вопросов, которые требовали вашего внимания. В сфере чувств Венера "
        "находится в напряжённом положении, поэтому лучше выбирать честность "
        "без резкости и не торопить разговоры."
    )

    message = build_daily_message(
        _user(),
        sign_ru="Скорпион",
        text_ru=long_text,
        energy={},
        message_date=date(2026, 5, 17),
    )

    # Must end with the unfinished-thought marker, NOT a full stop.
    assert message.rstrip().endswith("…")
    assert not message.rstrip().endswith((".", "!", "?"))
    # Generic "soft closer" phrases should be gone — they killed the cliffhanger.
    for soft_closer in (
        "Пусть день сложится без лишней спешки.",
        "Берегите темп и выбирайте то, что действительно важно.",
        "Пусть сегодня будет больше ясности, чем шума.",
    ):
        assert soft_closer not in message


def test_daily_message_short_horoscope_still_breaks_off():
    """Even when the horoscope is shorter than the target, we still want
    the ellipsis tail."""
    message = build_daily_message(
        _user(),
        sign_ru="Лев",
        text_ru="Сегодня лучше не спешить с выводами. Дайте темам дозреть.",
        energy={},
        message_date=date(2026, 5, 17),
    )
    assert message.rstrip().endswith("…")
