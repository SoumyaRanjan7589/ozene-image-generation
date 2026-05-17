from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from core.config import settings
from schemas.response import ErrorResponse, GenerationData, SuccessResponse
from services.fal_services import generate_images

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _error(code: int, message: str, errors: Optional[List[str]] = None):
    return JSONResponse(
        status_code=code,
        content=ErrorResponse(
            code=code, message=message, errors=errors
        ).model_dump(),
    )


async def _read_and_validate(
    upload: UploadFile, label: str
) -> tuple[bytes, str, str]:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{label}: unsupported type '{upload.content_type}'. "
                f"Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}"
            ),
        )
    data = await upload.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} exceeds {settings.MAX_FILE_SIZE_MB} MB limit.",
        )
    filename = upload.filename or label
    return data, upload.content_type, filename


@router.post(
    "/generate",
    response_model=SuccessResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Generation failed"},
    },
    summary="Generate composited image variants",
    description=(
        "Upload a base scene image and one or more object images with "
        "natural-language instructions. Returns multiple AI-generated variants."
    ),
)
async def generate(
    base_image: UploadFile = File(..., description="The background / scene image"),
    object_images: List[UploadFile] = File(
        ..., description="One or more object images to composite"
    ),
    instructions: str = Form(
        ...,
        description='e.g. "place the glass on the left side in black color"',
    ),
    num_images: int = Form(
        default=3,                    # ← default is now 3
        ge=1,
        le=4,
        description="Number of output variations (1–4)",
    ),
):
    if len(object_images) > settings.MAX_OBJECT_IMAGES:
        return _error(
            422,
            "Too many object images",
            [f"Maximum {settings.MAX_OBJECT_IMAGES} object images allowed."],
        )

    try:
        base_bytes, base_ct, base_name = await _read_and_validate(
            base_image, "base_image"
        )
        obj_tuples: List[tuple[bytes, str, str]] = []
        for idx, obj in enumerate(object_images, start=1):
            b, ct, name = await _read_and_validate(obj, f"object_image[{idx}]")
            obj_tuples.append((b, ct, name))
    except HTTPException as exc:
        return _error(exc.status_code, "Validation failed", [exc.detail])

    try:
        result = await generate_images(
            base_image_bytes=base_bytes,
            base_image_content_type=base_ct,
            object_images_bytes=obj_tuples,
            instructions=instructions,
            num_images=num_images,
        )
    except Exception as exc:
        return _error(500, "Image generation failed", [str(exc)])

    data = GenerationData(
        request_id=result["request_id"],
        instructions=instructions,
        generated_images=result["generated_images"],
        total_images=len(result["generated_images"]),
        model_used=settings.FAL_MODEL,
        processing_time_seconds=result["processing_time_seconds"],
        cost_estimate_usd=result["cost_estimate_usd"],   # ← new
    )

    return SuccessResponse(
        message=f"{data.total_images} image variant(s) generated successfully",
        data=data,
    )