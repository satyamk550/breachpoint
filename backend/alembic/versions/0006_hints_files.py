"""Add Phase 4b hints and secure challenge files."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table("hints", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("content", sa.Text, nullable=False), sa.Column("cost", sa.Integer, server_default="0", nullable=False), sa.Column("sort_order", sa.Integer, server_default="0", nullable=False), sa.Column("requires_hint_id", uuid, sa.ForeignKey("hints.id", ondelete="RESTRICT")), sa.CheckConstraint("cost >= 0", name="ck_hints_cost_nonnegative"))
    op.create_table("hint_unlocks", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("team_id", uuid, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("hint_id", uuid, sa.ForeignKey("hints.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("team_id", "hint_id", name="uq_hint_unlocks_team_hint"))
    op.create_table("challenge_files", sa.Column("id", uuid, server_default=sa.text("gen_random_uuid()"), primary_key=True), sa.Column("challenge_id", uuid, sa.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False), sa.Column("storage_name", sa.String(255), nullable=False, unique=True), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("size_bytes", sa.Integer, nullable=False), sa.Column("content_type", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

def downgrade() -> None:
    op.drop_table("challenge_files")
    op.drop_table("hint_unlocks")
    op.drop_table("hints")
