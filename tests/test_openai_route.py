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
