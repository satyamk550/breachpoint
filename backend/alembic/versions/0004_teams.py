"""Add Phase 3 team roster fields and limits.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("teams_invite_code_key", "teams", type_="unique")
    op.drop_column("teams", "invite_code")
    op.add_column("teams", sa.Column("join_secret_hash", sa.String(length=256), nullable=True))
    op.add_column(
        "teams",
        sa.Column("captain_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "teams", sa.Column("is_banned", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column(
        "teams", sa.Column("is_hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_foreign_key(
        "fk_teams_captain_id_users", "teams", "users", ["captain_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_teams_name_lower", "teams", [sa.text("lower(name)")], unique=True)
    op.alter_column("teams", "join_secret_hash", nullable=False)
    op.bulk_insert(
        sa.table("configs", sa.column("key", sa.String), sa.column("value", sa.Text)),
        [{"key": "team_size", "value": "4"}, {"key": "max_teams", "value": "25"}],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM configs WHERE key IN ('team_size', 'max_teams')"))
    op.drop_index("ix_teams_name_lower", table_name="teams")
    op.drop_constraint("fk_teams_captain_id_users", "teams", type_="foreignkey")
    op.drop_column("teams", "is_hidden")
    op.drop_column("teams", "is_banned")
    op.drop_column("teams", "captain_id")
    op.drop_column("teams", "join_secret_hash")
    op.add_column("teams", sa.Column("invite_code", sa.String(length=32), nullable=True))
    op.create_unique_constraint("teams_invite_code_key", "teams", ["invite_code"])
