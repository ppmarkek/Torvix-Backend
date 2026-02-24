import json
from urllib.error import URLError

from fastapi.testclient import TestClient

import app.api.routes.open_food_facts as open_food_facts_route
from app.main import app

client = TestClient(app)


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


def test_open_food_facts_product_success(monkeypatch) -> None:
    payload = {
        "status": 1,
        "product": {
            "product_name": "Coca-Cola Zero Sugar",
            "brands": "Coca-Cola",
            "quantity": "330 ml",
            "ingredients_text": "Water, sweeteners, caffeine",
            "image_front_url": "https://img.example/coke.jpg",
            "nutriscore_grade": "b",
            "ecoscore_grade": "d",
            "nova_group": 4,
            "nutriments": {
                "energy-kcal_100g": 0.2,
                "proteins_100g": 0,
                "fat_100g": 0,
                "saturated-fat_100g": 0,
                "carbohydrates_100g": 0,
                "sugars_100g": 0,
                "fiber_100g": 0,
                "salt_100g": 0.02,
                "sodium_100g": 0.008,
            },
        },
    }

    def fake_urlopen(*_args, **_kwargs):
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(open_food_facts_route, "urlopen", fake_urlopen)

    response = client.get("/api/open-food-facts/products/5449000000996")

    assert response.status_code == 200
    assert response.json() == {
        "barcode": "5449000000996",
        "productName": "Coca-Cola Zero Sugar",
        "brands": "Coca-Cola",
        "quantity": "330 ml",
        "ingredientsText": "Water, sweeteners, caffeine",
        "imageUrl": "https://img.example/coke.jpg",
        "nutriscoreGrade": "b",
        "ecoscoreGrade": "d",
        "novaGroup": 4,
        "nutriments": {
            "caloriesPer100g": 0.2,
            "proteinPer100g": 0.0,
            "fatPer100g": 0.0,
            "saturatedFatPer100g": 0.0,
            "carbsPer100g": 0.0,
            "sugarPer100g": 0.0,
            "fiberPer100g": 0.0,
            "saltPer100g": 0.02,
            "sodiumPer100g": 0.008,
        },
    }


def test_open_food_facts_product_success_by_post(monkeypatch) -> None:
    payload = {
        "status": 1,
        "product": {
            "product_name": "Coca-Cola Zero Sugar",
            "brands": "Coca-Cola",
            "quantity": "330 ml",
            "ingredients_text": "Water, sweeteners, caffeine",
            "image_front_url": "https://img.example/coke.jpg",
            "nutriscore_grade": "b",
            "ecoscore_grade": "d",
            "nova_group": 4,
            "nutriments": {},
        },
    }

    def fake_urlopen(*_args, **_kwargs):
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(open_food_facts_route, "urlopen", fake_urlopen)

    response = client.post(
        "/api/open-food-facts/product",
        json={"barcode": "5449000000996"},
    )

    assert response.status_code == 200
    assert response.json()["productName"] == "Coca-Cola Zero Sugar"


def test_open_food_facts_product_not_found(monkeypatch) -> None:
    payload = {"status": 0, "status_verbose": "product not found"}

    def fake_urlopen(*_args, **_kwargs):
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(open_food_facts_route, "urlopen", fake_urlopen)

    response = client.get("/api/open-food-facts/products/0000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


def test_open_food_facts_product_network_error(monkeypatch) -> None:
    def fake_urlopen(*_args, **_kwargs):
        raise URLError("network error")

    monkeypatch.setattr(open_food_facts_route, "urlopen", fake_urlopen)

    response = client.get("/api/open-food-facts/products/5449000000996")

    assert response.status_code == 502
    assert response.json() == {"detail": "Cannot reach Open Food Facts API"}


def test_open_food_facts_product_barcode_validation() -> None:
    response = client.get("/api/open-food-facts/products/not-a-barcode")

    assert response.status_code == 422
