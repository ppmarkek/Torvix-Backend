from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.api.routes.openai as openai_route
from app.api.routes.auth import get_current_user
from app.core.config import settings
from app.main import app
from app.models.user import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def override_current_user() -> Iterator[None]:
    def get_test_user() -> User:
        return User(
            id=1,
            email="openai@test.dev",
            name="OpenAI Tester",
            password_hash="hashed",
        )

    app.dependency_overrides[get_current_user] = get_test_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


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
    "fatSaturated": 12.4,
    "carbs": 18.5,
    "fiber": 2.1,
    "sugar": 3.8
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
    assert body["totalMacros"]["fatSaturated"] == 12.4
    assert body["totalMacros"]["sugar"] == 3.8
    assert body["ingredients"][0]["name"] == "Яйцо куриное жареное"
    assert captured_request["model"] == "gpt-5.2"
    assert "ru" in captured_request["input"][0]["content"][0]["text"]
    assert "fatSaturated" in captured_request["input"][0]["content"][0]["text"]
    assert "sugar" in captured_request["input"][0]["content"][0]["text"]
    assert captured_request["text"]["format"]["type"] == "json_schema"
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


def test_create_openai_response_maps_authentication_to_401(monkeypatch) -> None:
    class FakeAuthenticationError(Exception):
        status_code = 401
        body = {"error": {"message": "Invalid API key"}}

    class FakeResponses:
        def create(self, **_kwargs):
            raise FakeAuthenticationError("Invalid API key")

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr(openai_route, "AuthenticationError", FakeAuthenticationError)

    with pytest.raises(openai_route.HTTPException) as exc_info:
        openai_route._create_openai_response(FakeClient(), {"model": "gpt-5-mini", "input": "Hello"})

    assert exc_info.value.status_code == 401
    assert "OpenAI authentication failed" in exc_info.value.detail


def test_create_openai_response_propagates_upstream_4xx(monkeypatch) -> None:
    class FakeAPIStatusError(Exception):
        status_code = 403
        body = {"error": {"message": "Project has no access to this model"}}

    class FakeResponses:
        def create(self, **_kwargs):
            raise FakeAPIStatusError("Forbidden")

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr(openai_route, "APIStatusError", FakeAPIStatusError)

    with pytest.raises(openai_route.HTTPException) as exc_info:
        openai_route._create_openai_response(FakeClient(), {"model": "gpt-5-mini", "input": "Hello"})

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Project has no access to this model"


def test_create_openai_response_retries_with_higher_max_output_tokens() -> None:
    class FakeResponse:
        def __init__(self, *, status: str, reason: str | None = None, text: str = "") -> None:
            self.output_text = text
            self.status = status
            self.incomplete_details = {"reason": reason} if reason else None

        def model_dump(self, exclude_none: bool = True) -> dict:
            data = {
                "status": self.status,
                "output_text": self.output_text,
                "incomplete_details": self.incomplete_details,
            }
            if exclude_none:
                return {k: v for k, v in data.items() if v is not None}
            return data

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def create(self, **kwargs):
            self.calls.append(kwargs["max_output_tokens"])
            if len(self.calls) == 1:
                return FakeResponse(status="incomplete", reason="max_output_tokens")
            return FakeResponse(status="completed", text='{"ok": true}')

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    client = FakeClient()
    response = openai_route._create_openai_response(
        client,
        {"model": "gpt-5-mini", "input": "Hello", "max_output_tokens": 1200},
        max_output_token_retries=2,
    )

    assert response.output_text == '{"ok": true}'
    assert client.responses.calls == [1200, 2400]
