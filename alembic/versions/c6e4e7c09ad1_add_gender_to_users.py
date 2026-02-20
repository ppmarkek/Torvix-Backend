"""add gender to users

Revision ID: c6e4e7c09ad1
Revises: 8ed37e2dc3d2
Create Date: 2026-02-18 12:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c6e4e7c09ad1"
down_revision: Union[str, Sequence[str], None] = "8ed37e2dc3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    if bind.dialect.name == "postgresql":
        gender_enum = postgresql.ENUM("male", "female", name="gender", create_type=False)
        gender_enum.create(bind, checkfirst=True)
    else:
        gender_enum = sa.Enum("male", "female", name="gender")

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "gender" not in column_names:
        op.add_column("users", sa.Column("gender", gender_enum, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "gender" in column_names:
        op.drop_column("users", "gender")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="gender").drop(bind, checkfirst=True)
