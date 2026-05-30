"""Referral-code generation and lookup.

Codes are 8 lowercase-alphanumeric characters. They're URL-safe and short
enough to read aloud. We retry a few times on the (extremely unlikely)
collision before giving up so callers never see an "unlucky" failure.
"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from db.models import User

log = get_logger(__name__)

ALPHABET = string.ascii_lowercase + string.digits
CODE_LENGTH = 8
MAX_ATTEMPTS = 5


def generate_referral_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


async def get_or_create_referral_code(db: AsyncSession, user_id: int) -> str:
    """Idempotent — returns the user's existing code or mints a new one."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")
    if user.referral_code:
        return user.referral_code

    for _ in range(MAX_ATTEMPTS):
        candidate = generate_referral_code()
        existing = await db.execute(
            select(User.id).where(User.referral_code == candidate).limit(1)
        )
        if existing.scalar_one_or_none() is None:
            user.referral_code = candidate
            await db.flush()
            log.info("referral.code_generated", user_id=user_id, code=candidate)
            return candidate

    raise RuntimeError("Could not allocate a unique referral code after retries")
