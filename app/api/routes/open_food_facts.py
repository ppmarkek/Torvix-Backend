from __future__ import annotations

import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Path, status

from app.core.config import settings
from app.schemas.open_food_facts import (
    OpenFoodFactsBarcodeRequest,
    OpenFoodFactsNutriments,
    OpenFoodFactsProductResponse,
)

router = APIRouter(prefix="/api/open-food-facts", tags=["open-food-facts"])


def _as_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _as_string(data.get(key))
        if value is not None:
            return value
    return None


def _pick_first_float(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _as_float(data.get(key))
        if value is not None:
            return value
    return None


def _pick_first_int(data: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = _as_int(data.get(key))
        if value is not None:
            return value
    return None


def _load_product_payload(barcode: str) -> dict[str, Any]:
    base_url = settings.OPEN_FOOD_FACTS_BASE_URL.rstrip("/")
    request = Request(
        url=f"{base_url}/api/v2/product/{barcode}.json",
        headers={
            "Accept": "application/json",
            "User-Agent": "TorvixBackend/1.0",
        },
    )

    try:
        with urlopen(request, timeout=settings.OPEN_FOOD_FACTS_TIMEOUT_SECONDS) as response:
            response_bytes = response.read()
    except HTTPError as exc:
        if exc.code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Open Food Facts request failed",
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Open Food Facts request timed out",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot reach Open Food Facts API",
        ) from exc

    try:
        payload = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Open Food Facts returned invalid JSON",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Open Food Facts returned invalid JSON",
        )

    product = payload.get("product")
    if payload.get("status") != 1 or not isinstance(product, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


def _serialize_product(barcode: str, product: dict[str, Any]) -> OpenFoodFactsProductResponse:
    nutriments_data = product.get("nutriments")
    if not isinstance(nutriments_data, dict):
        nutriments_data = {}

    return OpenFoodFactsProductResponse(
        barcode=barcode,
        product_name=_pick_first_string(
            product, ("product_name", "product_name_ru", "product_name_en")
        ),
        brands=_as_string(product.get("brands")),
        quantity=_as_string(product.get("quantity")),
        ingredients_text=_pick_first_string(
            product,
            ("ingredients_text", "ingredients_text_ru", "ingredients_text_en"),
        ),
        image_url=_pick_first_string(product, ("image_front_url", "image_url")),
        nutriscore_grade=_as_string(product.get("nutriscore_grade")),
        ecoscore_grade=_as_string(product.get("ecoscore_grade")),
        nova_group=_pick_first_int(product, ("nova_group", "nova-group")),
        nutriments=OpenFoodFactsNutriments(
            calories_per_100g=_pick_first_float(
                nutriments_data, ("energy-kcal_100g", "energy-kcal")
            ),
            protein_per_100g=_pick_first_float(nutriments_data, ("proteins_100g",)),
            fat_per_100g=_pick_first_float(nutriments_data, ("fat_100g",)),
            saturated_fat_per_100g=_pick_first_float(
                nutriments_data, ("saturated-fat_100g",)
            ),
            carbs_per_100g=_pick_first_float(nutriments_data, ("carbohydrates_100g",)),
            sugar_per_100g=_pick_first_float(nutriments_data, ("sugars_100g",)),
            fiber_per_100g=_pick_first_float(nutriments_data, ("fiber_100g",)),
            salt_per_100g=_pick_first_float(nutriments_data, ("salt_100g",)),
            sodium_per_100g=_pick_first_float(nutriments_data, ("sodium_100g",)),
        ),
    )


@router.get("/products/{barcode}", response_model=OpenFoodFactsProductResponse)
def get_product_by_barcode(
    barcode: str = Path(..., pattern=r"^\d{8,24}$"),
) -> OpenFoodFactsProductResponse:
    product = _load_product_payload(barcode)
    return _serialize_product(barcode, product)


@router.post("/product", response_model=OpenFoodFactsProductResponse)
def get_product_by_payload(
    payload: OpenFoodFactsBarcodeRequest,
) -> OpenFoodFactsProductResponse:
    product = _load_product_payload(payload.barcode)
    return _serialize_product(payload.barcode, product)
