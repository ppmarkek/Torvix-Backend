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
