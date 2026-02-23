from pydantic import Field

from app.schemas.camel_model import CamelModel


class OpenAIChatRequest(CamelModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    system_prompt: str | None = Field(default=None, max_length=5_000)
    model: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=300, ge=1, le=4096)


class OpenAIChatResponse(CamelModel):
    model: str
    text: str


class IngredientMacrosPer100g(CamelModel):
    calories: float
    protein: float
    fat: float
    carbs: float


class TotalMacros(CamelModel):
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float


class DishIngredient(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0)
    weight_per_unit: float = Field(gt=0)
    macros_per_100g: IngredientMacrosPer100g


class FoodAnalysisResponse(CamelModel):
    dish_name: str = Field(min_length=1, max_length=300)
    total_weight: float = Field(gt=0)
    total_macros: TotalMacros
    ingredients: list[DishIngredient] = Field(min_length=1, max_length=30)

class SelfAddFoodRequest(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    weight_per_unit: float = Field(gt=0)
    additional_information: str = Field(max_length=5000)
