"""Launch monetization pack — welcome trial + referral program.

Revision ID: 012_launch_monetization
Revises: 011_transit_advice
Create Date: 2026-05-22

Adds:
- Subscription.is_trial / trial_reason — distinguish granted trials from paid subs.
- User.referral_code (unique) — the code shared via deep-link.
- User.referred_by — referrer's user id (FK to users).
- User.referred_by_processed, User.referred_purchase_processed — idempotency
  flags for the two-step referral rewards (Model B).
- New table `referral_rewards` — audit log of every Premium-day grant from
  the referral programme, with a unique (referrer, referee, event_type)
  constraint that doubles as a duplication guard.
"""

import sqlalchemy as sa
from alembic import op

revision = "012_launch_monetization"
down_revision = "011_transit_advice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Subscription: trial fields ───────────────────────────────────────────
    op.add_column(
        "subscriptions",
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "subscriptions",
        sa.Column("trial_reason", sa.String(length=32), nullable=True),
    )

    # ── User: referral fields ────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("referral_code", sa.String(length=16), nullable=True),
    )
    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])
    op.create_index("ix_users_referral_code", "users", ["referral_code"])

    op.add_column(
        "users",
        sa.Column("referred_by", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_referred_by",
        "users",
        "users",
        ["referred_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_referred_by", "users", ["referred_by"])

    op.add_column(
        "users",
        sa.Column(
            "referred_by_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "referred_purchase_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ── New table: referral_rewards ──────────────────────────────────────────
    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("referee_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("days_granted", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["referrer_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["referee_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "referrer_id",
            "referee_id",
            "event_type",
            name="uq_referral_event",
        ),
    )
    op.create_index(
        "ix_referral_rewards_referrer_id",
        "referral_rewards",
        ["referrer_id"],
    )
    op.create_index(
        "ix_referral_rewards_referee_id",
        "referral_rewards",
        ["referee_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_referral_rewards_referee_id", table_name="referral_rewards")
    op.drop_index("ix_referral_rewards_referrer_id", table_name="referral_rewards")
    op.drop_table("referral_rewards")

    op.drop_column("users", "referred_purchase_processed")
    op.drop_column("users", "referred_by_processed")
    op.drop_index("ix_users_referred_by", table_name="users")
    op.drop_constraint("fk_users_referred_by", "users", type_="foreignkey")
    op.drop_column("users", "referred_by")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referral_code")

    op.drop_column("subscriptions", "trial_reason")
    op.drop_column("subscriptions", "is_trial")
