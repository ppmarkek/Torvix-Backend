"""create meal statistics tables

Revision ID: 7a8d6e1c92bf
Revises: f2b7a9d14d32
Create Date: 2026-02-23 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a8d6e1c92bf"
down_revision: Union[str, Sequence[str], None] = "f2b7a9d14d32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "statistics_days" not in table_names:
        op.create_table(
            "statistics_days",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("day", sa.Date(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "day", name="uq_statistics_days_user_id_day"),
        )
        op.create_index("ix_statistics_days_user_id", "statistics_days", ["user_id"], unique=False)
        op.create_index("ix_statistics_days_day", "statistics_days", ["day"], unique=False)

    if "meal_entries" not in table_names:
        op.create_table(
            "meal_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("statistics_day_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("time", sa.DateTime(), nullable=False),
            sa.Column("dish_name", sa.String(length=300), nullable=False),
            sa.Column("total_weight", sa.Float(), nullable=False),
            sa.Column("total_macros", sa.JSON(), nullable=False),
            sa.Column("ingredients", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(["statistics_day_id"], ["statistics_days.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_meal_entries_statistics_day_id", "meal_entries", ["statistics_day_id"], unique=False)
        op.create_index("ix_meal_entries_user_id", "meal_entries", ["user_id"], unique=False)
        op.create_index("ix_meal_entries_time", "meal_entries", ["time"], unique=False)
        op.create_index("ix_meal_entries_dish_name", "meal_entries", ["dish_name"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "meal_entries" in table_names:
        index_names = {idx["name"] for idx in inspector.get_indexes("meal_entries")}
        if "ix_meal_entries_dish_name" in index_names:
            op.drop_index("ix_meal_entries_dish_name", table_name="meal_entries")
        if "ix_meal_entries_time" in index_names:
            op.drop_index("ix_meal_entries_time", table_name="meal_entries")
        if "ix_meal_entries_user_id" in index_names:
            op.drop_index("ix_meal_entries_user_id", table_name="meal_entries")
        if "ix_meal_entries_statistics_day_id" in index_names:
            op.drop_index("ix_meal_entries_statistics_day_id", table_name="meal_entries")
        op.drop_table("meal_entries")

    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    if "statistics_days" in table_names:
        index_names = {idx["name"] for idx in inspector.get_indexes("statistics_days")}
        if "ix_statistics_days_day" in index_names:
            op.drop_index("ix_statistics_days_day", table_name="statistics_days")
        if "ix_statistics_days_user_id" in index_names:
            op.drop_index("ix_statistics_days_user_id", table_name="statistics_days")
        op.drop_table("statistics_days")
