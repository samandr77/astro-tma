"""Single source of truth for all configuration. Values from env vars / .env file."""
from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # App
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_WEBHOOK_SECRET: str
    TELEGRAM_WEBHOOK_URL: str
    # URL the Mini App is served from — used in push notifications' inline
    # "Открыть в приложении" button (web_app field). Must be HTTPS and
    # configured as the bot's WebApp URL in @BotFather.
    TELEGRAM_WEBAPP_URL: str = "https://astro-tma.vercel.app/"

    # Push scheduling
    PUSH_DAILY_HOUR: int = 9

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"  # type: ignore[assignment]

    # Cache TTLs (seconds)
    CACHE_TTL_HOROSCOPE: int = 86400    # 24h
    CACHE_TTL_MOON: int = 3600          # 1h
    CACHE_TTL_NATAL: int = 604800       # 7d — natal never changes
    CACHE_TTL_TAROT_INTERPRET: int = 2592000  # 30d — readings are immutable

    # Admin panel — no defaults. If these are missing from .env, Pydantic
    # fails loudly at startup instead of booting with weak well-known creds
    # (SECURITY_AUDIT.md C2).
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # GeoNames
    GEONAMES_USERNAME: str = "demo"

    # Stars pricing — boot defaults match the launch monetization spec.
    # Production prices live in .env / admin Redis overrides.
    PRICE_TAROT_CELTIC: int = 29  # retired SKU, kept for back-compat
    PRICE_NATAL_FULL: int = 149
    PRICE_SYNASTRY: int = 79  # bumped from 49 (see UNIT_ECONOMICS.md §6)
    PRICE_DESTINY_MATRIX_FULL: int = 150
    PRICE_SUBSCRIPTION_MONTH: int = 199
    PRICE_SUBSCRIPTION_YEAR: int = 1490

    # Feature flags for launch pack — easy off-switch if something goes wrong.
    FEATURE_WELCOME_TRIAL: bool = True
    FEATURE_REFERRAL_PROGRAM: bool = True
    WELCOME_TRIAL_DAYS: int = 3
    REFERRAL_TRIAL_EXTENSION_DAYS: int = 4  # 3 + 4 = 7 total
    REFERRAL_FIRST_PURCHASE_BONUS_DAYS: int = 14

    # URL of the bot WebApp deeplink (e.g. "https://t.me/<bot>/app").
    # Used in referrer-reward Telegram notifications.
    MINIAPP_URL: str = ""

    # Feature flags
    FEATURE_PUSH_NOTIFICATIONS: bool = True
    FEATURE_SYNASTRY: bool = True

    # Dev-only: skip Telegram initData verification and inject a mock user.
    # Never honored in production.
    AUTH_BYPASS: bool = False
    AUTH_BYPASS_USER_ID: int = 777777777
    AUTH_BYPASS_FIRST_NAME: str = "Dev"

    @field_validator("APP_SECRET_KEY")
    @classmethod
    def secret_key_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("TELEGRAM_WEBHOOK_SECRET")
    @classmethod
    def webhook_secret_strength(cls, v: str) -> str:
        """SECURITY_AUDIT.md C3 — an empty TELEGRAM_WEBHOOK_SECRET turns the
        payments webhook into an open endpoint (anyone can POST a fake
        successful_payment). Require at least 16 chars of entropy."""
        if not v or len(v) < 16:
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must be set and at least 16 chars long"
            )
        return v

    @field_validator("ADMIN_PASSWORD")
    @classmethod
    def admin_password_strength(cls, v: str) -> str:
        """SECURITY_AUDIT.md C2 — reject the historic 'changeme' default and
        any obviously short password, even when read from .env."""
        if not v or len(v) < 12 or v.lower() in {"changeme", "admin", "password"}:
            raise ValueError(
                "ADMIN_PASSWORD is missing or too weak — set ≥12 random chars"
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

settings = get_settings()
