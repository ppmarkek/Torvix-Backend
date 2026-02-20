from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NutritionType = Literal["cooking", "logging"]
FoodCategory = Literal["generic-foods", "generic-meals", "packaged-foods", "fast-foods"]
HealthLabel = Literal[
    "alcohol-free",
    "celery-free",
    "crustacean-free",
    "dairy-free",
    "egg-free",
    "fish-free",
    "fodmap-free",
    "gluten-free",
    "immuno-supportive",
    "keto-friendly",
    "kidney-friendly",
    "kosher",
    "low-fat-abs",
    "low-potassium",
    "low-sugar",
    "lupine-free",
    "mustard-free",
    "no-oil-added",
    "paleo",
    "peanut-free",
    "pescatarian",
    "pork-free",
    "red-meat-free",
    "sesame-free",
    "shellfish-free",
    "soy-free",
    "sugar-conscious",
    "tree-nut-free",
    "vegan",
    "vegetarian",
    "wheat-free",
]


class AutoCompleteQueryParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    q: str = Field(min_length=1, description="Query text. Example: chi.")
    limit: int | None = Field(default=None, ge=1, description="Maximum suggestions.")


class NutrientsIngredient(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    quantity: float = Field(gt=0)
    measureURI: str = Field(min_length=1)
    foodId: str = Field(min_length=1)
    qualifiers: list[str] | None = None


class NutrientsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ingredients: list[NutrientsIngredient] = Field(min_length=1)


class NutrientsFromImageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    image: str | None = Field(
        default=None,
        description='Data URI image. Example: "data:image/jpeg;base64,..."',
    )
    image_url: str | None = Field(default=None, description="Public image URL.")

    @model_validator(mode="after")
    def _validate_image_source(self) -> "NutrientsFromImageRequest":
        if not self.image and not self.image_url:
            raise ValueError("Either image or image_url must be provided")
        return self
