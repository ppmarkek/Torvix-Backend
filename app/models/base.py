from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

def utcnow():
    return datetime.now(timezone.utc)

class BaseTable(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)