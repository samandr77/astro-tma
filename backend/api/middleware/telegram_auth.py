"""
Telegram WebApp initData verification.

Telegram sends initData string to Mini App at launch.
We verify it using HMAC-SHA256 to ensure it hasn't been tampered with.
See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

This is the ONLY auth mechanism for the app — no JWT, no sessions.
Every request carries initData and we verify on the backend.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException, status

from core.logging import get_logger
from core.settings import settings

log = get_logger(__name__)

_MAX_AGE_SECONDS = 86400  # reject initData older than 24 hours


def verify_init_data(init_data: str) -> dict:
    """
    Verify Telegram initData string and return parsed user data.

    Raises HTTPException 401 if verification fails.
    Returns dict with 'user' key on success.
    """
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed initData")

    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash in initData")

    # Check timestamp freshness
    auth_date = params.get("auth_date", "0")
    if int(time.time()) - int(auth_date) >= _MAX_AGE_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")

    # Build data-check string: sorted key=value pairs joined by \n
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # HMAC key = HMAC("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData",
        settings.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        log.warning("auth.invalid_hash", auth_date=auth_date)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid initData signature")

    # Parse user JSON
    user_json = params.get("user", "{}")
    try:
        user = json.loads(unquote(user_json))
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed user data")

    return {"user": user, "params": params}


async def get_tg_user(
    x_init_data: str = Header("", alias="X-Init-Data"),
) -> dict:
    """
    FastAPI dependency: extract and verify Telegram user from request header.

    Usage:
        @router.get("/")
        async def endpoint(tg_user: dict = Depends(get_tg_user)):
            user_id = tg_user["id"]
    """
    # Dev-only auth bypass. SECURITY_AUDIT.md C1: require an explicit
    # APP_ENV=development match (not just "not production") so a typo in
    # APP_ENV cannot silently re-enable the bypass.
    if (
        settings.AUTH_BYPASS
        and settings.APP_ENV == "development"
        and not settings.is_production
    ):
        log.warning(
            "auth.bypass_active ⚠ DEV MODE — auth is OFF",
            user_id=settings.AUTH_BYPASS_USER_ID,
            env=settings.APP_ENV,
        )
        return {
            "id": settings.AUTH_BYPASS_USER_ID,
            "first_name": settings.AUTH_BYPASS_FIRST_NAME,
            "last_name": "",
            "username": "dev_user",
            "language_code": "ru",
            "is_premium": False,
        }
    if settings.AUTH_BYPASS and settings.is_production:
        # Misconfiguration: AUTH_BYPASS=true in prod. Fail closed loudly.
        log.error("auth.bypass_blocked_in_production")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Server misconfigured — refusing to serve",
        )

    if not x_init_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Init-Data header")

    verified = verify_init_data(x_init_data)
    user = verified["user"]

    if not user.get("id"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No user ID in initData")

    return user
