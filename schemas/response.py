from pydantic import BaseModel
from typing import List, Optional


class GeneratedImage(BaseModel):
    index: int
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


class GenerationData(BaseModel):
    request_id: str
    instructions: str
    generated_images: List[GeneratedImage]
    total_images: int
    model_used: str
    processing_time_seconds: float
    cost_estimate_usd: float          # ← new


class SuccessResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str
    data: GenerationData


class ErrorResponse(BaseModel):
    success: bool = False
    code: int
    message: str
    errors: Optional[List[str]] = None