"""Russian zodiac sign names and common case forms."""

from __future__ import annotations

from typing import Any, Literal

SIGN_RU: dict[str, str] = {
    "aries": "Овен",
    "taurus": "Телец",
    "gemini": "Близнецы",
    "cancer": "Рак",
    "leo": "Лев",
    "virgo": "Дева",
    "libra": "Весы",
    "scorpio": "Скорпион",
    "sagittarius": "Стрелец",
    "capricorn": "Козерог",
    "aquarius": "Водолей",
    "pisces": "Рыбы",
}

_PREPOSITIONAL: dict[str, str] = {
    "aries": "Овне",
    "taurus": "Тельце",
    "gemini": "Близнецах",
    "cancer": "Раке",
    "leo": "Льве",
    "virgo": "Деве",
    "libra": "Весах",
    "scorpio": "Скорпионе",
    "sagittarius": "Стрельце",
    "capricorn": "Козероге",
    "aquarius": "Водолее",
    "pisces": "Рыбах",
}

_GENITIVE: dict[str, str] = {
    "aries": "Овна",
    "taurus": "Тельца",
    "gemini": "Близнецов",
    "cancer": "Рака",
    "leo": "Льва",
    "virgo": "Девы",
    "libra": "Весов",
    "scorpio": "Скорпиона",
    "sagittarius": "Стрельца",
    "capricorn": "Козерога",
    "aquarius": "Водолея",
    "pisces": "Рыб",
}

SignCase = Literal["nom", "prep", "gen"]


def sign_key(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in SIGN_RU:
        return key
    reverse = {name.lower(): sign for sign, name in SIGN_RU.items()}
    reverse.update({name.lower(): sign for sign, name in _PREPOSITIONAL.items()})
    reverse.update({name.lower(): sign for sign, name in _GENITIVE.items()})
    return reverse.get(key, key)


def sign_ru(value: Any, case: SignCase = "nom") -> str:
    key = sign_key(value)
    if case == "prep":
        return _PREPOSITIONAL.get(key, str(value or ""))
    if case == "gen":
        return _GENITIVE.get(key, str(value or ""))
    return SIGN_RU.get(key, str(value or ""))
