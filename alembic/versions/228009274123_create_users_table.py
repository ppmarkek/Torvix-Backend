"""create users table

Revision ID: 228009274123
Revises: 
Create Date: 2026-02-16 16:15:11.276901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '228009274123'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        weight_metric_enum = postgresql.ENUM("kg", "lbs", "st", name="weightmetric", create_type=False)
        height_metric_enum = postgresql.ENUM("cm", "ft_in", name="heightmetric", create_type=False)
        goal_enum = postgresql.ENUM("lose_fat", "maintain", "muscle_gain", name="goal", create_type=False)
        weight_metric_enum.create(bind, checkfirst=True)
        height_metric_enum.create(bind, checkfirst=True)
        goal_enum.create(bind, checkfirst=True)
    else:
        weight_metric_enum = sa.Enum("kg", "lbs", "st", name="weightmetric")
        height_metric_enum = sa.Enum("cm", "ft_in", name="heightmetric")
        goal_enum = sa.Enum("lose_fat", "maintain", "muscle_gain", name="goal")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("weight_metric", weight_metric_enum, nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("height_metric", height_metric_enum, nullable=True),
        sa.Column("what_do_you_want_to_achieve", goal_enum, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        index_names = {idx["name"] for idx in inspector.get_indexes("users")}
        if "ix_users_email" in index_names:
            op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="goal").drop(bind, checkfirst=True)
        postgresql.ENUM(name="heightmetric").drop(bind, checkfirst=True)
        postgresql.ENUM(name="weightmetric").drop(bind, checkfirst=True)
