import os
from dotenv import load_dotenv
load_dotenv()
os.environ["FAL_KEY"] = os.getenv("FAL_KEY", "")

import fal_client
import asyncio
import time
import uuid
import random
from typing import List

from app.schemas.response import GeneratedImage

PRICE_PER_MP_USD = 0.03  # flux-2-pro/edit pricing


def _build_prompt(instructions: str, num_object_images: int) -> str:
    """
    FLUX.2 pro/edit understands image indexing.
    image_1 = base scene (bathroom)
    image_2, image_3... = object images (glass, mirror etc)
    We reference them explicitly by index in the prompt.
    """
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


async def upload_image_to_fal(image_bytes: bytes, content_type: str) -> str:
    """Upload image bytes to fal storage, get back a public URL."""
    import io
    loop = asyncio.get_event_loop()

    def _upload():
        return fal_client.upload(
            io.BytesIO(image_bytes),
            content_type=content_type,
        )

    return await loop.run_in_executor(None, _upload)


async def generate_images(
    base_image_bytes: bytes,
    base_image_content_type: str,
    object_images_bytes: List[tuple[bytes, str, str]],
    instructions: str,
    num_images: int = 3,
) -> dict:
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Step 1 — Upload ALL images to fal storage in parallel
    # base image + all object images uploaded simultaneously
    upload_tasks = [
        upload_image_to_fal(base_image_bytes, base_image_content_type)
    ] + [
        upload_image_to_fal(img_bytes, ct)
        for img_bytes, ct, _ in object_images_bytes
    ]

    all_urls = await asyncio.gather(*upload_tasks)
    base_url = all_urls[0]
    object_urls = list(all_urls[1:])

    # Step 2 — Build prompt referencing images by index
    prompt = _build_prompt(instructions, len(object_urls))

    # Step 3 — Build image_urls list: base first, then objects
    # FLUX.2 pro/edit references them as image_1, image_2, image_3...
    all_image_urls = [base_url] + object_urls

    loop = asyncio.get_event_loop()

    def _call_fal(seed: int):
        return fal_client.subscribe(
            "fal-ai/flux-2-pro/edit",    # multi-image compositing model
            arguments={
                "prompt": prompt,
                "image_urls": all_image_urls,  # list: [base, obj1, obj2...]
                "strength": 0.85,              # how much to change (0=nothing, 1=everything)
                "seed": seed,
            },
            with_logs=False,
        )

    # Step 4 — Run num_images parallel calls with different seeds
    seeds = [random.randint(1, 2**31) for _ in range(num_images)]
    tasks = [
        loop.run_in_executor(None, _call_fal, seed)
        for seed in seeds
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 5 — Parse results
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
        raise Exception(
            "All generation attempts failed. Check logs above for details."
        )

    processing_time = round(time.time() - start_time, 2)
    # flux-2-pro/edit: $0.03 per MP, 1024x1024 = ~1MP
    cost = round(len(generated_images) * PRICE_PER_MP_USD, 4)

    return {
        "request_id": request_id,
        "generated_images": generated_images,
        "processing_time_seconds": processing_time,
        "cost_estimate_usd": cost,
        "seeds_used": seeds,
    }