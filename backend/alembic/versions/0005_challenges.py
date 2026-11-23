"""Add Phase 4a challenge domain."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("categories", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("name", sa.String(128), nullable=False), sa.Column("sort_order", sa.Integer, server_default="0", nullable=False), sa.UniqueConstraint("name"))
    op.create_table("challenges", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("description_md", sa.Text, nullable=False), sa.Column("category_id", uuid, sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False), sa.Column("points", sa.Integer, server_default="0", nullable=False), sa.Column("scoring_mode", sa.String(16), server_default="static", nullable=False), sa.Column("initial", sa.Integer, server_default="0", nullable=False), sa.Column("minimum", sa.Integer, server_default="0", nullable=False), sa.Column("decay", sa.Float, server_default="1", nullable=False), sa.Column("function", sa.String(32), server_default="linear", nullable=False), sa.Column("visibility", sa.String(16), server_default="draft", nullable=False), sa.Column("max_attempts", sa.Integer), sa.Column("connection_info", sa.Text), sa.Column("author", sa.String(128)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("points >= 0", name="ck_challenges_points_nonnegative"), sa.CheckConstraint("initial >= minimum", name="ck_challenges_initial_gte_minimum"), sa.CheckConstraint("decay > 0", name="ck_challenges_decay_positive"), sa.CheckConstraint("max_attempts IS NULL OR max_attempts >= 1", name="ck_challenges_max_attempts_positive"))
    op.create_table("flags", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("type", sa.String(16), nullable=False), sa.Column("content", sa.String(500), nullable=False), sa.Column("case_insensitive", sa.Boolean, server_default=sa.text("false"), nullable=False))
    op.create_table("tags", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("value", sa.String(64), nullable=False), sa.UniqueConstraint("challenge_id", "value", name="uq_tags_challenge_value"))
    op.create_table("challenge_prerequisites", sa.Column("challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True), sa.Column("requires_challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True), sa.CheckConstraint("challenge_id <> requires_challenge_id", name="ck_prerequisite_not_self"))
    op.create_table("solves", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("team_id", uuid, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("team_id", "challenge_id", name="uq_solves_team_challenge"))

def downgrade() -> None:
    op.drop_table("solves"); op.drop_table("challenge_prerequisites"); op.drop_table("tags"); op.drop_table("flags"); op.drop_table("challenges"); op.drop_table("categories")
