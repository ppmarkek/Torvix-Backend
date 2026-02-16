from datetime import datetime

from sqlmodel import Field

from app.models.base import BaseTable


class AuthSession(BaseTable, table=True):
    __tablename__: str = "auth_sessions"  # type: ignore[assignment]

    user_id: int = Field(nullable=False, foreign_key="users.id", index=True)
    refresh_token_hash: str = Field(nullable=False, unique=True, index=True, max_length=64)
    expires_at: datetime = Field(nullable=False, index=True)
    revoked_at: datetime | None = Field(default=None, index=True)
