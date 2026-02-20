from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Annotated, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.food_database import (
    AutoCompleteQueryParams,
    FoodCategory,
    HealthLabel,
    NutritionType,
    NutrientsFromImageRequest,
    NutrientsRequest,
)

router = APIRouter(prefix="/api/food-database", tags=["food-database"])
compat_router = APIRouter(tags=["food-database"])
AccountUserHeader = Annotated[str | None, Header(alias="Edamam-Account-User")]
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _assert_credentials() -> None:
    if settings.FOOD_DATABASE_API_ID and settings.FOOD_DATABASE_API_KEY:
        return

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Missing FOOD_DATABASE_API_ID or FOOD_DATABASE_API_KEY",
    )


def _query_items_from_mapping(data: Mapping[str, Any]) -> list[tuple[str, str]]:
    query_items: list[tuple[str, str]] = []
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, list):
            query_items.extend((key, str(item)) for item in value)
            continue
        if isinstance(value, bool):
            query_items.append((key, "true" if value else "false"))
            continue
        query_items.append((key, str(value)))

    return query_items


def _with_credentials(query_items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [
        *query_items,
        ("app_id", settings.FOOD_DATABASE_API_ID),
        ("app_key", settings.FOOD_DATABASE_API_KEY),
    ]


def _edamam_url(path: str, query_items: list[tuple[str, str]]) -> str:
    base_url = settings.EDAMAM_URL.rstrip("/")
    query_string = urlencode(query_items, doseq=True)
    return f"{base_url}{path}?{query_string}"


def _error_detail(raw_error: str, fallback: str) -> str:
    if not raw_error:
        return fallback

    try:
        parsed_error = json.loads(raw_error)
    except json.JSONDecodeError:
        return raw_error[:300]

    if isinstance(parsed_error, dict):
        return (
            parsed_error.get("message")
            or parsed_error.get("error")
            or parsed_error.get("detail")
            or fallback
        )

    if isinstance(parsed_error, list) and parsed_error:
        first_error = parsed_error[0]
        if isinstance(first_error, dict):
            return (
                first_error.get("message")
                or first_error.get("error")
                or first_error.get("errorCode")
                or fallback
            )

    return fallback


def _edamam_headers(
    edamam_account_user: str | None = None,
    content_type: str | None = None,
) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    if edamam_account_user:
        headers["Edamam-Account-User"] = edamam_account_user
    if content_type:
        headers["Content-Type"] = content_type
    return headers or None


def _call_edamam(
    target_url: str,
    method: str = "GET",
    request_body: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    method = method.upper()
    headers = {"Accept": "application/json"}
    if extra_headers is not None:
        headers.update(extra_headers)
    outbound_request = Request(
        target_url,
        data=request_body if method != "GET" else None,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(outbound_request, timeout=15) as response:
            raw_body = response.read()
            response_status = response.getcode() or status.HTTP_200_OK
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="ignore")
        detail = _error_detail(raw_error, "Edamam Food Database request failed")
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Edamam Food Database request timed out",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot reach Edamam Food Database API",
        ) from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from Edamam Food Database API",
        ) from exc

    return JSONResponse(content=payload, status_code=response_status)


def _image_url_to_data_uri(image_url: str) -> str:
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_url must use http or https",
        )

    image_request = Request(
        image_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TorvixBackend/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    try:
        with urlopen(image_request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
            if not content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="image_url must point to an image resource",
                )

            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Image is too large (max {MAX_IMAGE_BYTES} bytes)",
                    )
                chunks.append(chunk)
    except HTTPException:
        raise
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot download image_url (HTTP {exc.code})",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot download image_url",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Timed out while downloading image_url",
        ) from exc

    image_bytes = b"".join(chunks)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _parser_query_items(
    ingr: str | None = Query(
        default=None,
        description="Food name keyword. Required if both brand and upc are not provided.",
    ),
    brand: str | None = Query(
        default=None,
        description="Brand keyword. Required if both ingr and upc are not provided.",
    ),
    upc: str | None = Query(
        default=None,
        description="UPC/EAN/PLU code. If provided, ingr and brand must be omitted.",
    ),
    nutrition_type: Annotated[
        NutritionType,
        Query(alias="nutrition-type", description="Select between cooking and logging."),
    ] = "cooking",
    health: Annotated[
        list[HealthLabel] | None,
        Query(description="Health labels filter."),
    ] = None,
    calories: str | None = Query(
        default=None,
        description="Range format: MIN+, MIN-MAX or MAX.",
    ),
    category: Annotated[
        list[FoodCategory] | None,
        Query(description="Category filters."),
    ] = None,
    nutrients_ca: str | None = Query(default=None, alias="nutrients[CA]"),
    nutrients_chocdf: str | None = Query(default=None, alias="nutrients[CHOCDF]"),
    nutrients_chocdf_net: str | None = Query(default=None, alias="nutrients[CHOCDF.net]"),
    nutrients_chole: str | None = Query(default=None, alias="nutrients[CHOLE]"),
    nutrients_enerc_kcal: str | None = Query(default=None, alias="nutrients[ENERC_KCAL]"),
    nutrients_fams: str | None = Query(default=None, alias="nutrients[FAMS]"),
    nutrients_fapu: str | None = Query(default=None, alias="nutrients[FAPU]"),
    nutrients_fasat: str | None = Query(default=None, alias="nutrients[FASAT]"),
    nutrients_fat: str | None = Query(default=None, alias="nutrients[FAT]"),
    nutrients_fatrn: str | None = Query(default=None, alias="nutrients[FATRN]"),
    nutrients_fe: str | None = Query(default=None, alias="nutrients[FE]"),
    nutrients_fibtg: str | None = Query(default=None, alias="nutrients[FIBTG]"),
    nutrients_folac: str | None = Query(default=None, alias="nutrients[FOLAC]"),
    nutrients_foldfe: str | None = Query(default=None, alias="nutrients[FOLDFE]"),
    nutrients_folfd: str | None = Query(default=None, alias="nutrients[FOLFD]"),
    nutrients_k: str | None = Query(default=None, alias="nutrients[K]"),
    nutrients_mg: str | None = Query(default=None, alias="nutrients[MG]"),
    nutrients_na: str | None = Query(default=None, alias="nutrients[NA]"),
    nutrients_nia: str | None = Query(default=None, alias="nutrients[NIA]"),
    nutrients_p: str | None = Query(default=None, alias="nutrients[P]"),
    nutrients_procnt: str | None = Query(default=None, alias="nutrients[PROCNT]"),
    nutrients_ribf: str | None = Query(default=None, alias="nutrients[RIBF]"),
    nutrients_sugar: str | None = Query(default=None, alias="nutrients[SUGAR]"),
    nutrients_sugar_added: str | None = Query(default=None, alias="nutrients[SUGAR.added]"),
    nutrients_sugar_alcohol: str | None = Query(default=None, alias="nutrients[Sugar.alcohol]"),
    nutrients_thia: str | None = Query(default=None, alias="nutrients[THIA]"),
    nutrients_tocpha: str | None = Query(default=None, alias="nutrients[TOCPHA]"),
    nutrients_vita_rae: str | None = Query(default=None, alias="nutrients[VITA_RAE]"),
    nutrients_vitb12: str | None = Query(default=None, alias="nutrients[VITB12]"),
    nutrients_vitb6a: str | None = Query(default=None, alias="nutrients[VITB6A]"),
    nutrients_vitc: str | None = Query(default=None, alias="nutrients[VITC]"),
    nutrients_vitd: str | None = Query(default=None, alias="nutrients[VITD]"),
    nutrients_vitk1: str | None = Query(default=None, alias="nutrients[VITK1]"),
    nutrients_water: str | None = Query(default=None, alias="nutrients[WATER]"),
    nutrients_zn: str | None = Query(default=None, alias="nutrients[ZN]"),
) -> list[tuple[str, str]]:
    if not any((ingr, brand, upc)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One of ingr, brand, or upc is required",
        )

    if upc and (ingr or brand):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="upc cannot be combined with ingr or brand",
        )

    query_data: dict[str, Any] = {
        "ingr": ingr,
        "brand": brand,
        "upc": upc,
        "nutrition-type": nutrition_type,
        "health": health,
        "calories": calories,
        "category": category,
        "nutrients[CA]": nutrients_ca,
        "nutrients[CHOCDF]": nutrients_chocdf,
        "nutrients[CHOCDF.net]": nutrients_chocdf_net,
        "nutrients[CHOLE]": nutrients_chole,
        "nutrients[ENERC_KCAL]": nutrients_enerc_kcal,
        "nutrients[FAMS]": nutrients_fams,
        "nutrients[FAPU]": nutrients_fapu,
        "nutrients[FASAT]": nutrients_fasat,
        "nutrients[FAT]": nutrients_fat,
        "nutrients[FATRN]": nutrients_fatrn,
        "nutrients[FE]": nutrients_fe,
        "nutrients[FIBTG]": nutrients_fibtg,
        "nutrients[FOLAC]": nutrients_folac,
        "nutrients[FOLDFE]": nutrients_foldfe,
        "nutrients[FOLFD]": nutrients_folfd,
        "nutrients[K]": nutrients_k,
        "nutrients[MG]": nutrients_mg,
        "nutrients[NA]": nutrients_na,
        "nutrients[NIA]": nutrients_nia,
        "nutrients[P]": nutrients_p,
        "nutrients[PROCNT]": nutrients_procnt,
        "nutrients[RIBF]": nutrients_ribf,
        "nutrients[SUGAR]": nutrients_sugar,
        "nutrients[SUGAR.added]": nutrients_sugar_added,
        "nutrients[Sugar.alcohol]": nutrients_sugar_alcohol,
        "nutrients[THIA]": nutrients_thia,
        "nutrients[TOCPHA]": nutrients_tocpha,
        "nutrients[VITA_RAE]": nutrients_vita_rae,
        "nutrients[VITB12]": nutrients_vitb12,
        "nutrients[VITB6A]": nutrients_vitb6a,
        "nutrients[VITC]": nutrients_vitc,
        "nutrients[VITD]": nutrients_vitd,
        "nutrients[VITK1]": nutrients_vitk1,
        "nutrients[WATER]": nutrients_water,
        "nutrients[ZN]": nutrients_zn,
    }
    return _query_items_from_mapping(query_data)


@router.get("/v2/parser")
def parser(
    query_items: Annotated[list[tuple[str, str]], Depends(_parser_query_items)],
    edamam_account_user: AccountUserHeader = None,
) -> JSONResponse:
    _assert_credentials()
    target_url = _edamam_url("/api/food-database/v2/parser", _with_credentials(query_items))
    return _call_edamam(
        target_url,
        extra_headers=_edamam_headers(edamam_account_user),
    )


@router.post("/v2/nutrients")
def nutrients(
    payload: NutrientsRequest,
    edamam_account_user: AccountUserHeader = None,
) -> JSONResponse:
    _assert_credentials()
    query_items = _with_credentials([])
    target_url = _edamam_url("/api/food-database/v2/nutrients", query_items)
    body = payload.model_dump_json(by_alias=True).encode("utf-8")
    return _call_edamam(
        target_url,
        method="POST",
        request_body=body,
        extra_headers=_edamam_headers(
            edamam_account_user=edamam_account_user,
            content_type="application/json",
        ),
    )


def _post_nutrients_from_image(
    payload: NutrientsFromImageRequest,
    beta: Literal[True],
    edamam_account_user: str | None,
) -> JSONResponse:
    _assert_credentials()
    effective_beta = beta
    query_items = _with_credentials(
        _query_items_from_mapping({"beta": effective_beta})
    )
    target_url = _edamam_url("/api/food-database/nutrients-from-image", query_items)
    body_payload = payload.model_dump(by_alias=True, exclude_none=True)
    body = json.dumps(body_payload).encode("utf-8")

    try:
        return _call_edamam(
            target_url,
            method="POST",
            request_body=body,
            extra_headers=_edamam_headers(
                edamam_account_user=edamam_account_user,
                content_type="application/json",
            ),
        )
    except HTTPException as exc:
        if (
            exc.status_code == status.HTTP_400_BAD_REQUEST
            and isinstance(exc.detail, str)
            and "Invalid image" in exc.detail
            and payload.image is None
            and payload.image_url is not None
        ):
            data_uri = _image_url_to_data_uri(payload.image_url)
            fallback_body = json.dumps({"image": data_uri}).encode("utf-8")
            return _call_edamam(
                target_url,
                method="POST",
                request_body=fallback_body,
                extra_headers=_edamam_headers(
                    edamam_account_user=edamam_account_user,
                    content_type="application/json",
                ),
            )
        raise


@router.post("/v2/nutrients-from-image", include_in_schema=False)
@router.post("/nutrients-from-image")
def nutrients_from_image(
    payload: NutrientsFromImageRequest,
    beta: Literal[True] = Query(
        default=True,
        description="Allow beta features in request and response. Defaults to true.",
    ),
    edamam_account_user: AccountUserHeader = None,
) -> JSONResponse:
    return _post_nutrients_from_image(payload, beta, edamam_account_user)


@compat_router.post("/nutrients-from-image", include_in_schema=False)
def nutrients_from_image_compat(
    payload: NutrientsFromImageRequest,
    beta: Literal[True] = True,
    edamam_account_user: AccountUserHeader = None,
) -> JSONResponse:
    return _post_nutrients_from_image(payload, beta, edamam_account_user)


@router.get("/auto-complete")
def auto_complete(
    params: Annotated[AutoCompleteQueryParams, Depends()],
    edamam_account_user: AccountUserHeader = None,
) -> JSONResponse:
    _assert_credentials()
    query_items = _with_credentials(
        _query_items_from_mapping(params.model_dump(by_alias=True, exclude_none=True))
    )
    target_url = _edamam_url("/auto-complete", query_items)
    return _call_edamam(
        target_url,
        extra_headers=_edamam_headers(edamam_account_user),
    )
