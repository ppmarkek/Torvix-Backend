from datetime import date, datetime

from pydantic import Field

from app.models.user import ActivityLevel, Gender, Goal, HeightMetric, WeightMetric
from app.schemas.camel_model import CamelModel

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserCreate(CamelModel):
    email: str = Field(min_length=5, max_length=255, pattern=EMAIL_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=255)

    birth_date: date | None = None
    weight: float | None = Field(default=None, gt=0)
    weight_metric: WeightMetric | None = None
    height: float | None = Field(default=None, gt=0)
    height_metric: HeightMetric | None = None
    gender: Gender | None = None
    activity_level: ActivityLevel | None = None
    what_do_you_want_to_achieve: Goal | None = None


class UserUpdate(CamelModel):
    email: str | None = Field(default=None, min_length=5, max_length=255, pattern=EMAIL_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=255)

    birth_date: date | None = None
    weight: float | None = Field(default=None, gt=0)
    weight_metric: WeightMetric | None = None
    height: float | None = Field(default=None, gt=0)
    height_metric: HeightMetric | None = None
    gender: Gender | None = None
    activity_level: ActivityLevel | None = None
    what_do_you_want_to_achieve: Goal | None = None


class UserRead(CamelModel):
    id: int
    email: str
    name: str

    birth_date: date | None = None
    weight: float | None = None
    weight_metric: WeightMetric | None = None
    height: float | None = None
    height_metric: HeightMetric | None = None
    gender: Gender | None = None
    activity_level: ActivityLevel | None = None
    what_do_you_want_to_achieve: Goal | None = None

    created_at: datetime
    updated_at: datetime


class UserLogin(CamelModel):
    email: str = Field(min_length=5, max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=255)


class TokenResponse(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class EmailExists(CamelModel):
    email: str = Field(min_length=5, max_length=255, pattern=EMAIL_PATTERN)


class EmailExistsResponse(CamelModel):
    email: str
    exists: bool


class RefreshTokenRequest(CamelModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class LogoutResponse(CamelModel):
    success: bool = True
