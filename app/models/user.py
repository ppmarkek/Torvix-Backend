from datetime import date
from enum import Enum
from sqlmodel import Field
from app.models.base import BaseTable


class WeightMetric(str, Enum):
    kg = "kg"
    lbs = "lbs"
    st = "st"


class HeightMetric(str, Enum):
    cm = "cm"
    ft_in = "ft_in"


class Goal(str, Enum):
    lose_fat = "lose_fat"
    maintain = "maintain"
    muscle_gain = "muscle_gain"

class User(BaseTable, table=True):
    __tablename__: str = "users" # type: ignore[assignment]

    email: str = Field(index=True, unique=True, nullable=False, max_length=255)
    name: str = Field(nullable=False, max_length=255)
    password_hash: str = Field(nullable=False, max_length=255)

    birth_date: date | None = Field(default=None)

    weight: float | None = Field(default=None)
    weight_metric: WeightMetric | None = Field(default=None)

    height: float | None = Field(default=None)
    height_metric: HeightMetric | None = Field(default=None)

    what_do_you_want_to_achieve: Goal | None = Field(default=None)
