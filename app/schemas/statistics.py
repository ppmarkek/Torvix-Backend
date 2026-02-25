from datetime import date, datetime

from pydantic import Field

from app.schemas.camel_model import CamelModel


class IngredientMacrosPer100g(CamelModel):
    calories: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    fat: float | None = Field(default=None, ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fiber: float | None = Field(default=None, ge=0)


class MealIngredient(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    weight_per_unit: float | None = Field(default=None, gt=0)
    quantity: float | None = Field(default=None, gt=0)
    macros_per_100g: IngredientMacrosPer100g | None = None


class MealTotalMacros(CamelModel):
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    fat: float = Field(ge=0)
    fat_saturated: float | None = Field(default=None, ge=0)
    carbs: float = Field(ge=0)
    fiber: float = Field(ge=0)
    sugar: float | None = Field(default=None, ge=0)


class MealCreate(CamelModel):
    time: datetime
    dish_name: str = Field(min_length=1, max_length=300)
    total_weight: float = Field(gt=0)
    total_macros: MealTotalMacros
    ingredients: list[MealIngredient] = Field(default_factory=list, max_length=100)


class MealRead(CamelModel):
    id: int
    time: datetime
    dish_name: str
    total_weight: float
    total_macros: MealTotalMacros
    ingredients: list[MealIngredient]


class StatisticsDayRead(CamelModel):
    day: date
    meals: list[MealRead]


class StatisticsRead(CamelModel):
    days: list[StatisticsDayRead]


class DishNameRead(CamelModel):
    id: int
    dish_name: str


class DishNamesRead(CamelModel):
    dish_names: list[DishNameRead]


class MealsByDishRead(CamelModel):
    dish_id: int
    dish_name: str
    meals: list[MealRead]
