"""Add Phase 2 account security fields and reset tokens.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.add_column("users", sa.Column("is_banned", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_index("ix_users_username_lower", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_banned")
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.create_unique_constraint("users_username_key", "users", ["username"])
