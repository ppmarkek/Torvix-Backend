from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.models.base import BaseTable


class StatisticsDay(BaseTable, table=True):
    __tablename__: str = "statistics_days"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_statistics_days_user_id_day"),
    )

    user_id: int = Field(nullable=False, foreign_key="users.id", index=True)
    day: date = Field(nullable=False, index=True)


class MealEntry(BaseTable, table=True):
    __tablename__: str = "meal_entries"  # type: ignore[assignment]

    statistics_day_id: int = Field(nullable=False, foreign_key="statistics_days.id", index=True)
    user_id: int = Field(nullable=False, foreign_key="users.id", index=True)
    time: datetime = Field(nullable=False, index=True)
    dish_name: str = Field(nullable=False, index=True, max_length=300)
    total_weight: float = Field(nullable=False)
    total_macros: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    ingredients: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
