"""Destiny Matrix v2 — switch to book-validated calculator.

Formula set + arcana contexts changed:
- positions JSONB structure is now {personality, ancestral_square, lines,
  purposes, channels, varna} — completely incompatible with the v1 shape
- arcana_meanings contexts went from 8 (personality, mission, money, love,
  health, karma, shadow, advice) to 9 (personality, talents, purpose,
  parental, ancestral, relationships, finance, material_karma, karmic_tail)

Therefore: TRUNCATE all three tables. Users will recompute on next
/calculate (pure-math, fast). LLM interpretations regenerate on demand.
Purchase records (premium access) are NOT touched.

Revision ID: 014_destiny_matrix_v2
Revises: 013_destiny_matrix
Create Date: 2026-05-30
"""

from alembic import op

revision = "014_destiny_matrix_v2"
down_revision = "013_destiny_matrix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Order matters — interpretations FK→readings (CASCADE), but TRUNCATE
    # CASCADE handles it. arcana_meanings is independent.
    op.execute("TRUNCATE TABLE destiny_matrix_interpretations RESTART IDENTITY CASCADE")
    op.execute("TRUNCATE TABLE destiny_matrix_readings RESTART IDENTITY CASCADE")
    op.execute("TRUNCATE TABLE arcana_meanings RESTART IDENTITY CASCADE")


def downgrade() -> None:
    # Irreversible — data is gone. Leaving as a no-op rather than pretending
    # to restore something.
    pass
