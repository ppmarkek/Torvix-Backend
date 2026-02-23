from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

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
from app.schemas.openai import (
    FoodPhotoAnalysisResponse,
    OpenAIChatRequest,
    OpenAIChatResponse,
)

router = APIRouter(prefix="/api/openai", tags=["openai"])
MAX_IMAGE_BYTES = 8 * 1024 * 1024
SUPPORTED_LANGUAGE_CODES = {
    "en": "English",
    "ru": "Russian",
    "lv": "Latvian",
    "fr": "French",
    "de": "German",
    "nl": "Dutch",
    "it": "Italian",
    "es": "Spanish",
    "pt": "Portuguese",
    "sv": "Swedish",
    "da": "Danish",
    "nb": "Norwegian Bokmal",
    "fi": "Finnish",
    "is": "Icelandic",
    "pl": "Polish",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "ro": "Romanian",
    "uk": "Ukrainian",
    "be": "Belarusian",
    "lt": "Lithuanian",
    "et": "Estonian",
}


def _assert_openai_installed() -> None:
    if OpenAI is not None:
        return

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="openai package is not installed. Run `poetry install`.",
    )


def _create_openai_client() -> Any:
    if OpenAI is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openai package is not installed. Run `poetry install`.",
        )
    return OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL)


def _assert_credentials() -> None:
    if settings.OPENAI_API_KEY:
        return

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Missing OPENAI_API_KEY",
    )


def _bad_request_detail(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message
    return str(exc)


def _create_openai_response(client: Any, request_params: dict[str, Any]) -> Any:
    effective_params = dict(request_params)
    for attempt in range(2):
        try:
            return client.responses.create(**effective_params)
        except BadRequestError as exc:
            message = _bad_request_detail(exc)
            # Some models reject temperature; retry once without it.
            if (
                attempt == 0
                and "Unsupported parameter: 'temperature'" in message
                and "temperature" in effective_params
            ):
                effective_params.pop("temperature", None)
                continue
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            ) from exc
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

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="OpenAI API request failed",
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


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI returned invalid JSON",
            )

        try:
            parsed = json.loads(raw_text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OpenAI returned invalid JSON",
            ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid JSON",
        )

    return parsed


def _resolve_language_code(language: str) -> tuple[str, str]:
    language_code = language.strip().lower()
    if language_code in SUPPORTED_LANGUAGE_CODES:
        return language_code, SUPPORTED_LANGUAGE_CODES[language_code]

    supported_codes = ", ".join(SUPPORTED_LANGUAGE_CODES.keys())
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unsupported language code. Use one of: {supported_codes}",
    )


def _food_photo_instructions(language_code: str, language_name: str) -> str:
    return (
        "Analyze the meal photo and estimate nutrition.\n"
        f"Use language code `{language_code}` ({language_name}) for `dishName` and every ingredient `name`.\n"
        "Return ONLY valid JSON. Do not use markdown or extra text.\n"
        "Required schema:\n"
        "{"
        '"dishName": string,'
        '"totalWeight": number,'
        '"totalMacros": {"calories": number, "protein": number, "fat": number, "carbs": number, "fiber": number},'
        '"ingredients": ['
        '{"name": string, "quantity": number, "weightPerUnit": number, "macrosPer100g": {"calories": number, "protein": number, "fat": number, "carbs": number}}'
        "]"
        "}\n"
        "All numbers must be positive. Do not add fields outside this schema."
    )


@router.post("/chat", response_model=OpenAIChatResponse)
def chat(payload: OpenAIChatRequest) -> OpenAIChatResponse:
    _assert_openai_installed()
    _assert_credentials()
    model_name = payload.model or settings.OPENAI_MODEL
    client = _create_openai_client()
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

    response = _create_openai_response(client, request_params)

    response_model = getattr(response, "model", model_name)
    return OpenAIChatResponse(
        model=response_model,
        text=_extract_text(response),
    )


@router.post("/food-photo", response_model=FoodPhotoAnalysisResponse)
async def food_photo(
    file: UploadFile = File(...),
    language: str = Form(..., min_length=2, max_length=8),
    model: str | None = Form(default=None, min_length=1),
) -> FoodPhotoAnalysisResponse:
    _assert_openai_installed()
    _assert_credentials()

    language_code, language_name = _resolve_language_code(language)

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file must be an image",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file is empty",
        )
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image is too large (max {MAX_IMAGE_BYTES} bytes)",
        )

    data_uri = f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    model_name = model or settings.OPENAI_MODEL
    client = _create_openai_client()
    request_params: dict[str, Any] = {
        "model": model_name,
        "max_output_tokens": 1200,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": _food_photo_instructions(language_code, language_name),
                    },
                    {"type": "input_image", "image_url": data_uri},
                ],
            }
        ],
    }
    response = _create_openai_response(client, request_params)
    raw_text = _extract_text(response)
    parsed_response = _extract_json_object(raw_text)

    try:
        return FoodPhotoAnalysisResponse.model_validate(parsed_response)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned invalid nutrition format",
        ) from exc
