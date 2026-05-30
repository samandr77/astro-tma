from core.settings import Settings


def test_settings_ignores_compose_only_env_vars(tmp_path, monkeypatch):
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_SECRET_KEY=change-me-to-32-plus-random-chars-xxxxxxxxxxx",
                "TELEGRAM_BOT_TOKEN=1234567890:AABBccDDeeFFggHHiiJJkkLLmmNNoo",
                "TELEGRAM_WEBHOOK_SECRET=random-secret-for-webhook-verification",
                "TELEGRAM_WEBHOOK_URL=https://api.example.test/webhook",
                "DATABASE_URL=postgresql+asyncpg://astro:yourpassword@postgres:5432/astro_tma",
                "POSTGRES_PASSWORD=yourpassword",
            ]
        )
    )

    settings = Settings(_env_file=env_file)

    assert settings.DATABASE_URL.unicode_string().endswith("/astro_tma")
