"""Destiny Matrix feature — tables for arcana lookup, per-user readings,
and lazily generated LLM interpretations.

Revision ID: 013_destiny_matrix
Revises: 012_launch_monetization
Create Date: 2026-05-26
"""

import sqlalchemy as sa
from alembic import op

revision = "013_destiny_matrix"
down_revision = "012_launch_monetization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── arcana_meanings: 22 arcana × 8 contexts = 176 text blocks ─────────
    # Filled by infra/scripts/seed_destiny_arcana.py — kept in a dedicated
    # table (separate from `tarot_cards`) because the Destiny Matrix uses
    # the Marseille numbering (8=Justice, 11=Strength), which is different
    # from the Rider-Waite deck the tarot module uses.
    op.create_table(
        "arcana_meanings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arcana_num", sa.SmallInteger(), nullable=False),
        sa.Column("arcana_name", sa.Text(), nullable=False),
        sa.Column("context", sa.String(length=32), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("keywords", sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.CheckConstraint("arcana_num BETWEEN 1 AND 22", name="ck_arcana_num_range"),
        sa.UniqueConstraint("arcana_num", "context", name="uq_arcana_num_context"),
    )
    op.create_index(
        "idx_arcana_num_ctx", "arcana_meanings", ["arcana_num", "context"]
    )

    # ── destiny_matrix_readings: per-user computed matrix ─────────────────
    # Idempotent on (user_id, birth_date) — when the user updates their
    # birth date in profile, the matrix is recomputed but the row from the
    # previous birth date stays for history.
    op.create_table(
        "destiny_matrix_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("positions", sa.JSON(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "birth_date", name="uq_dm_user_birthdate"),
    )
    op.create_index("idx_dm_user", "destiny_matrix_readings", ["user_id"])

    # ── destiny_matrix_interpretations: cached LLM narrative ──────────────
    # Lazily generated on first request to /destiny-matrix/interpretation;
    # cached forever per reading_id. Stored separately from the readings
    # table so a quick `SELECT * FROM destiny_matrix_readings` doesn't drag
    # multi-kilobyte JSON.
    op.create_table(
        "destiny_matrix_interpretations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "reading_id",
            sa.Integer(),
            sa.ForeignKey("destiny_matrix_readings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("reading_id", name="uq_dm_interp_reading"),
    )


def downgrade() -> None:
    op.drop_table("destiny_matrix_interpretations")
    op.drop_index("idx_dm_user", table_name="destiny_matrix_readings")
    op.drop_table("destiny_matrix_readings")
    op.drop_index("idx_arcana_num_ctx", table_name="arcana_meanings")
    op.drop_table("arcana_meanings")
