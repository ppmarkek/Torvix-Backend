"""add activity level to users

Revision ID: f2b7a9d14d32
Revises: c6e4e7c09ad1
Create Date: 2026-02-18 13:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f2b7a9d14d32"
down_revision: Union[str, Sequence[str], None] = "c6e4e7c09ad1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        activity_level_enum = postgresql.ENUM(
            "minimal",
            "light",
            "medium",
            "high",
            "very_high",
            name="activitylevel",
            create_type=False,
        )
        activity_level_enum.create(bind, checkfirst=True)
    else:
        activity_level_enum = sa.Enum(
            "minimal",
            "light",
            "medium",
            "high",
            "very_high",
            name="activitylevel",
        )

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "activity_level" not in column_names:
        op.add_column("users", sa.Column("activity_level", activity_level_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "activity_level" in column_names:
        op.drop_column("users", "activity_level")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="activitylevel").drop(bind, checkfirst=True)
