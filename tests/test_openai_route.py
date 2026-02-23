from fastapi.testclient import TestClient

import app.api.routes.openai as openai_route
from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_openai_chat_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    response = client.post("/api/openai/chat", json={"prompt": "Hello"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Missing OPENAI_API_KEY"}


def test_openai_chat_success(monkeypatch) -> None:
    class FakeResponse:
        model = "gpt-test"
        output_text = "Hi from OpenAI"

    class FakeResponses:
        def create(self, **_kwargs):
            return FakeResponse()

    class FakeOpenAIClient:
        def __init__(self, **_kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setattr(openai_route, "OpenAI", FakeOpenAIClient)

    response = client.post("/api/openai/chat", json={"prompt": "Hello"})

    assert response.status_code == 200
    assert response.json() == {"model": "gpt-test", "text": "Hi from OpenAI"}


def test_openai_food_photo_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    response = client.post(
        "/api/openai/food-photo",
        data={"language": "ru"},
        files={"file": ("food.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Missing OPENAI_API_KEY"}


def test_openai_food_photo_success(monkeypatch) -> None:
    captured_request: dict = {}

    class FakeResponse:
        model = "gpt-5.2"
        output_text = """
{
  "dishName": "Яичница с беконом и тостами",
  "totalWeight": 250,
  "totalMacros": {
    "calories": 480,
    "protein": 25.5,
    "fat": 40.2,
    "carbs": 18.5,
    "fiber": 2.1
  },
  "ingredients": [
    {
      "name": "Яйцо куриное жареное",
      "quantity": 2,
      "weightPerUnit": 55,
      "macrosPer100g": {
        "calories": 204,
        "protein": 13.9,
        "fat": 15.6,
        "carbs": 1.2
      }
    }
  ]
}
""".strip()

    class FakeResponses:
        def create(self, **kwargs):
            captured_request.update(kwargs)
            return FakeResponse()

    class FakeOpenAIClient:
        def __init__(self, **_kwargs):
            self.responses = FakeResponses()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-5-mini")
    monkeypatch.setattr(openai_route, "OpenAI", FakeOpenAIClient)

    response = client.post(
        "/api/openai/food-photo",
        data={"language": "ru", "model": "gpt-5.2"},
        files={"file": ("food.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dishName"] == "Яичница с беконом и тостами"
    assert body["totalWeight"] == 250
    assert body["totalMacros"]["calories"] == 480
    assert body["ingredients"][0]["name"] == "Яйцо куриное жареное"
    assert captured_request["model"] == "gpt-5.2"
    assert "ru" in captured_request["input"][0]["content"][0]["text"]
    assert captured_request["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")


def test_openai_food_photo_rejects_unsupported_language(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    response = client.post(
        "/api/openai/food-photo",
        data={"language": "jp"},
        files={"file": ("food.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )

    assert response.status_code == 422
    assert "Unsupported language code" in response.json()["detail"]
