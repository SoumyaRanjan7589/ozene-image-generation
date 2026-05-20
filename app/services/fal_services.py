import os
from dotenv import load_dotenv
load_dotenv()

import fal_client
import asyncio
import time
import uuid
import random
from typing import List

from app.core.config import settings
from app.schemas.response import GeneratedImage

PRICE_PER_IMAGE_USD = 0.04


def _build_prompt(instructions: str, num_object_images: int) -> str:
    if num_object_images == 1:
        return (
            f"Using image_1 as the base scene, place the object from image_2 into the scene. "
            f"{instructions}. "
            "Keep the rest of the scene exactly the same. "
            "Maintain realistic lighting, shadows, and perspective. "
            "The object should look naturally placed, not pasted."
        )
    else:
        object_refs = ", ".join([f"image_{i+2}" for i in range(num_object_images)])
        return (
            f"Using image_1 as the base scene, place the objects from {object_refs} into the scene. "
            f"{instructions}. "
            "Keep the rest of the scene exactly the same. "
            "Maintain realistic lighting, shadows, and perspective. "
            "All objects should look naturally placed, not pasted."
        )


def _upload_with_key(image_bytes: bytes, content_type: str, api_key: str) -> str:
    """Upload image using a specific API key."""
    import io
    os.environ["FAL_KEY"] = api_key
    return fal_client.upload(
        io.BytesIO(image_bytes),
        content_type=content_type,
    )


def _call_fal_with_key(model: str, payload: dict, api_key: str):
    """Call fal.ai using a specific API key."""
    os.environ["FAL_KEY"] = api_key
    return fal_client.subscribe(
        model,
        arguments=payload,
        with_logs=False,
    )


async def upload_image_with_fallback(image_bytes: bytes, content_type: str) -> str:
    """Upload image, trying each key until one succeeds."""
    keys = settings.get_active_keys()
    loop = asyncio.get_event_loop()
    last_error = None

    for idx, key in enumerate(keys, start=1):
        try:
            url = await loop.run_in_executor(
                None, _upload_with_key, image_bytes, content_type, key
            )
            return url
        except Exception as e:
            last_error = e
            print(f"Upload failed with key {idx}: {e}. Trying next key...")
            continue

    raise Exception(f"All API keys failed during upload. Last error: {last_error}")


def _call_fal_with_fallback(model: str, payload: dict, seed: int) -> dict:
    """Call fal.ai with fallback across keys."""
    keys = settings.get_active_keys()
    last_error = None

    for idx, key in enumerate(keys, start=1):
        try:
            payload["seed"] = seed
            result = _call_fal_with_key(model, payload, key)
            return result
        except Exception as e:
            last_error = e
            print(f"Generation failed with key {idx}: {e}. Trying next key...")
            continue

    raise Exception(f"All API keys failed during generation. Last error: {last_error}")


async def generate_images(
    base_image_bytes: bytes,
    base_image_content_type: str,
    object_images_bytes: List[tuple[bytes, str, str]],
    instructions: str,
    num_images: int = 3,
) -> dict:
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Upload all images with fallback
    upload_tasks = [
        upload_image_with_fallback(base_image_bytes, base_image_content_type)
    ] + [
        upload_image_with_fallback(img_bytes, ct)
        for img_bytes, ct, _ in object_images_bytes
    ]
    all_urls = await asyncio.gather(*upload_tasks)
    base_url = all_urls[0]
    object_urls = list(all_urls[1:])

    prompt = _build_prompt(instructions, len(object_urls))

    all_image_urls = [base_url] + object_urls

    payload = {
        "prompt": prompt,
        "image_urls": all_image_urls,
        "strength": 0.85,
        "output_format": "jpeg",
    }

    loop = asyncio.get_event_loop()
    seeds = [random.randint(1, 2**31) for _ in range(num_images)]

    # Run parallel calls — each with key fallback
    tasks = [
        loop.run_in_executor(
            None, _call_fal_with_fallback, settings.FAL_MODEL, dict(payload), seed
        )
        for seed in seeds
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    generated_images: List[GeneratedImage] = []
    index = 1

    for result in results:
        if isinstance(result, Exception):
            print(f"Generation attempt failed: {result}")
            continue
        for img in result.get("images", []):
            generated_images.append(
                GeneratedImage(
                    index=index,
                    url=img.get("url", ""),
                    width=img.get("width"),
                    height=img.get("height"),
                )
            )
            index += 1

    if not generated_images:
        raise Exception("All generation attempts failed across all API keys.")

    processing_time = round(time.time() - start_time, 2)
    cost = round(len(generated_images) * PRICE_PER_IMAGE_USD, 4)

    return {
        "request_id": request_id,
        "generated_images": generated_images,
        "processing_time_seconds": processing_time,
        "cost_estimate_usd": cost,
        "seeds_used": seeds,
    }