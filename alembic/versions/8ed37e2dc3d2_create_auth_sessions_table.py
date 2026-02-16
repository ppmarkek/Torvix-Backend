"""create auth sessions table

Revision ID: 8ed37e2dc3d2
Revises: 228009274123
Create Date: 2026-02-16 17:04:16.446452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ed37e2dc3d2'
down_revision: Union[str, Sequence[str], None] = '228009274123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "auth_sessions" in inspector.get_table_names():
        return

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    op.create_index("ix_auth_sessions_refresh_token_hash", "auth_sessions", ["refresh_token_hash"], unique=True)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "auth_sessions" not in inspector.get_table_names():
        return

    index_names = {idx["name"] for idx in inspector.get_indexes("auth_sessions")}
    if "ix_auth_sessions_revoked_at" in index_names:
        op.drop_index("ix_auth_sessions_revoked_at", table_name="auth_sessions")
    if "ix_auth_sessions_expires_at" in index_names:
        op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    if "ix_auth_sessions_refresh_token_hash" in index_names:
        op.drop_index("ix_auth_sessions_refresh_token_hash", table_name="auth_sessions")
    if "ix_auth_sessions_user_id" in index_names:
        op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
