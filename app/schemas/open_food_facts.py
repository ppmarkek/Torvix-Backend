from pydantic import Field

from app.schemas.camel_model import CamelModel


class OpenFoodFactsBarcodeRequest(CamelModel):
    barcode: str = Field(pattern=r"^\d{8,24}$")


class OpenFoodFactsNutriments(CamelModel):
    calories_per_100g: float | None = None
    protein_per_100g: float | None = None
    fat_per_100g: float | None = None
    saturated_fat_per_100g: float | None = None
    carbs_per_100g: float | None = None
    sugar_per_100g: float | None = None
    fiber_per_100g: float | None = None
    salt_per_100g: float | None = None
    sodium_per_100g: float | None = None


class OpenFoodFactsProductResponse(CamelModel):
    barcode: str
    product_name: str | None = None
    brands: str | None = None
    quantity: str | None = None
    ingredients_text: str | None = None
    image_url: str | None = None
    nutriscore_grade: str | None = None
    ecoscore_grade: str | None = None
    nova_group: int | None = None
    nutriments: OpenFoodFactsNutriments
