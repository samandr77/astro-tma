"""Destiny Matrix V2 — arcana_meanings extended (gender + plus/minus/professions).

Adds:
    * `gender` — 'any' / 'male' / 'female'. Most rows are 'any' (gender-neutral
      meaning); male/female rows act as overrides for arcana whose tone
      shifts with the reader's gender (3, 4, relationships, parental).
    * `plus` — short positive expression of the arcana on this position.
    * `minus` — short shadow expression.
    * `professions` — gender-neutral career hints (only meaningful for the
      finance / material_karma contexts; nullable otherwise).

Unique constraint moves to `(arcana_num, context, gender)` so the same
context can have an `any` row + a male and a female override.

Existing data is truncated — the V2 seeder regenerates everything anyway
and the cached LLM interpretations stay valid (they don't depend on this
table's structure).

Revision ID: 015_arcana_v2_gender
Revises: 014_destiny_matrix_v2
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from alembic import op

revision = "015_arcana_v2_gender"
down_revision = "014_destiny_matrix_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("TRUNCATE TABLE arcana_meanings RESTART IDENTITY")

    op.add_column(
        "arcana_meanings",
        sa.Column(
            "gender",
            sa.String(8),
            nullable=False,
            server_default="any",
        ),
    )
    op.add_column("arcana_meanings", sa.Column("plus", sa.Text, nullable=True))
    op.add_column("arcana_meanings", sa.Column("minus", sa.Text, nullable=True))
    op.add_column("arcana_meanings", sa.Column("professions", sa.Text, nullable=True))

    op.drop_constraint("uq_arcana_num_context", "arcana_meanings", type_="unique")
    op.create_unique_constraint(
        "uq_arcana_num_context_gender",
        "arcana_meanings",
        ["arcana_num", "context", "gender"],
    )

    op.drop_index("idx_arcana_num_ctx", table_name="arcana_meanings")
    op.create_index(
        "idx_arcana_num_ctx_gender",
        "arcana_meanings",
        ["arcana_num", "context", "gender"],
    )


def downgrade() -> None:
    # Irreversible without losing V2 content — leave as no-op.
    pass
