"""Add Phase 5 submissions, scoring events, awards, and first blood."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column(
        "solves",
        sa.Column("is_first_blood", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "submissions",
        sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", uuid, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "challenge_id",
            uuid,
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("provided_value", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip", sa.String(64), nullable=False),
    )
    op.create_table(
        "awards",
        sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", uuid, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_by",
            uuid,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("value <> 0", name="ck_awards_value_nonzero"),
    )
    op.create_table(
        "score_events",
        sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("team_id", uuid, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column(
            "challenge_id",
            uuid,
            sa.ForeignKey("challenges.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('solve', 'hint', 'award', 'adjustment')",
            name="ck_score_events_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("score_events")
    op.drop_table("awards")
    op.drop_table("submissions")
    op.drop_column("solves", "is_first_blood")
