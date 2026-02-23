from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

try:
    from openai import (
        APIConnectionError,
        APIError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        RateLimitError,
    )
except ImportError:
    APIConnectionError = APIError = APITimeoutError = AuthenticationError = Exception
    BadRequestError = RateLimitError = Exception
    OpenAI = None

from app.core.config import settings
from app.schemas.openai import OpenAIChatRequest, OpenAIChatResponse

router = APIRouter(prefix="/api/openai", tags=["openai"])


def _assert_credentials() -> None:
    if settings.OPENAI_API_KEY:
        return

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Missing OPENAI_API_KEY",
    )


def _extract_text(response: Any) -> str:
    direct_text = getattr(response, "output_text", None)
    if isinstance(direct_text, str):
        text = direct_text.strip()
        if text:
            return text

    output_items = getattr(response, "output", None)
    if isinstance(output_items, list):
        text_parts: list[str] = []
        for output_item in output_items:
            content_items = getattr(output_item, "content", None)
            if not isinstance(content_items, list):
                continue
            for content_item in content_items:
                content_text = getattr(content_item, "text", None)
                if isinstance(content_text, str):
                    text_parts.append(content_text)

        merged_text = "".join(text_parts).strip()
        if merged_text:
            return merged_text

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="OpenAI returned an empty response",
    )


@router.post("/chat", response_model=OpenAIChatResponse)
def chat(payload: OpenAIChatRequest) -> OpenAIChatResponse:
    if OpenAI is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openai package is not installed. Run `poetry install`.",
        )

    _assert_credentials()
    model_name = payload.model or settings.OPENAI_MODEL
    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)
    request_params: dict[str, Any] = {
        "model": model_name,
        "input": payload.prompt,
    }
    if payload.system_prompt is not None:
        request_params["instructions"] = payload.system_prompt
    if payload.temperature is not None:
        request_params["temperature"] = payload.temperature
    if payload.max_output_tokens is not None:
        request_params["max_output_tokens"] = payload.max_output_tokens

    try:
        response = client.responses.create(**request_params)
    except BadRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI authentication failed",
        ) from exc
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI rate limit exceeded",
        ) from exc
    except APITimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="OpenAI request timed out",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot reach OpenAI API",
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI API request failed",
        ) from exc

    response_model = getattr(response, "model", model_name)
    return OpenAIChatResponse(
        model=response_model,
        text=_extract_text(response),
    )
