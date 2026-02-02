"""API routers for Image API - OpenAI compatible endpoints."""

import asyncio
import base64
import functools
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from PIL import Image
import io

from image_api.models import MODEL_REGISTRY, get_status_manager
from image_api.queue import TaskType, get_task_queue
from image_api.downloader import ModelDownloader
from image_api.utils.gpu import get_gpu_info, get_quantization_recommendation
from .model import get_model_instance


logger = logging.getLogger(__name__)
router = APIRouter()
executor = ThreadPoolExecutor(max_workers=4)


# ============================================================================
# Request/Response Models
# ============================================================================


class ImageGenerationRequest(BaseModel):
    """OpenAI compatible image generation request."""

    model: str = Field(default="stable-diffusion-3.5-medium")
    prompt: str = Field(..., description="Text description of the image to generate")
    n: int = Field(default=1, ge=1, le=10, description="Number of images to generate")
    size: str = Field(
        default="1024x1024", description="Image size (e.g., 1024x1024, 512x512)"
    )
    quality: str = Field(default="standard", description="Image quality")
    response_format: str = Field(
        default="url", description="Response format: url or b64_json"
    )
    style: Optional[str] = Field(default=None, description="Image style")
    user: Optional[str] = Field(default=None, description="User identifier")

    # Extended parameters (not in OpenAI API)
    negative_prompt: Optional[str] = Field(
        default=None, description="Text to avoid in the image"
    )
    steps: int = Field(
        default=28, ge=1, le=100, description="Number of inference steps"
    )
    guidance_scale: float = Field(
        default=3.5, ge=0, le=20, description="Guidance scale"
    )
    seed: Optional[int] = Field(default=None, description="Random seed")


class ImageEditRequest(BaseModel):
    """OpenAI compatible image edit request (image-to-image)."""

    model: str = Field(default="stable-diffusion-3.5-medium")
    prompt: str = Field(..., description="Text description of the desired output")
    n: int = Field(default=1, ge=1, le=10)
    size: str = Field(default="1024x1024")
    response_format: str = Field(default="url")

    # Extended parameters
    negative_prompt: Optional[str] = None
    strength: float = Field(default=0.8, ge=0, le=1)
    steps: int = Field(default=28, ge=1, le=100)
    guidance_scale: float = Field(default=3.5, ge=0, le=20)
    seed: Optional[int] = None


class ImageData(BaseModel):
    """Single image data in response."""

    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageGenerationResponse(BaseModel):
    """OpenAI compatible image generation response."""

    created: int
    data: List[ImageData]


class ModelInfo(BaseModel):
    """Model information response."""

    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "image-api"


class ModelsListResponse(BaseModel):
    """List of models response."""

    object: str = "list"
    data: List[dict]


class QueueTaskResponse(BaseModel):
    """Queue task response."""

    task_id: str
    status: str
    position: int
    message: str


# ============================================================================
# Helper Functions
# ============================================================================


def parse_size(size: str) -> tuple:
    """Parse size string to width and height."""
    try:
        parts = size.lower().split("x")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 1024, 1024


async def run_in_executor(func, *args, **kwargs):
    """Run a blocking function in executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor, functools.partial(func, *args, **kwargs)
    )


def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================================
# Health & Info Endpoints
# ============================================================================


@router.get("/health")
async def health():
    """Health check endpoint."""
    instance = get_model_instance()
    if instance is None or not instance.is_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ok"}


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Image API",
        "version": "0.1.0",
        "description": "Text-to-image and image-to-image server compatible with OpenAI API",
    }


@router.get("/v1/gpu")
async def get_gpu_status():
    """Get GPU information and recommended quantization."""
    gpu_info = get_gpu_info()
    recommendation = get_quantization_recommendation(gpu_info.get("total_memory_gb", 0))

    return {
        "gpu": gpu_info,
        "quantization_recommendation": recommendation,
        "quantization_strategy": {
            "int4": "< 10GB VRAM - 4-bit NF4 quantization",
            "int8": "10-20GB VRAM - 8-bit quantization",
            "fp16": "> 20GB VRAM - Full FP16 precision",
        },
    }


# ============================================================================
# Models Endpoints
# ============================================================================


@router.get("/v1/models", response_model=ModelsListResponse)
async def list_models():
    """List all available models with their status."""
    status_manager = get_status_manager()
    models = MODEL_REGISTRY.list_all()

    data = []
    for model in models:
        info = model.to_dict()
        if status_manager:
            runtime_status = status_manager.get_status(model.name)
            info["status"] = runtime_status.to_dict()
        data.append(info)

    return {"object": "list", "data": data}


@router.get("/v1/models/{model_id}")
async def get_model(model_id: str):
    """Get information about a specific model."""
    model = MODEL_REGISTRY.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    info = model.to_dict()
    status_manager = get_status_manager()
    if status_manager:
        runtime_status = status_manager.get_status(model_id)
        info["status"] = runtime_status.to_dict()

    return info


@router.post("/v1/models/{model_id}/download")
async def download_model(model_id: str, force: bool = False):
    """Download a model."""
    model = MODEL_REGISTRY.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    instance = get_model_instance()
    if not instance:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Get model directory from config
    model_dir = instance._config.model_dir

    downloader = ModelDownloader(
        model_dir=model_dir,
        huggingface_repo_id=model.hf_repo if model.hf_repo else None,
        model_scope_model_id=model.modelscope if model.modelscope else None,
    )

    # Start async download
    def do_download():
        return downloader.download(force=force)

    try:
        path = await run_in_executor(do_download)
        return {
            "status": "completed",
            "model": model_id,
            "path": path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Image Generation Endpoints (OpenAI Compatible)
# ============================================================================


@router.post("/v1/images/generations", response_model=ImageGenerationResponse)
async def create_image(request: ImageGenerationRequest):
    """
    Generate images from text prompt.

    OpenAI compatible endpoint for text-to-image generation.
    """
    instance = get_model_instance()
    if not instance or not instance.is_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")

    width, height = parse_size(request.size)

    # Create task for queue
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = task_queue.add_task(
        TaskType.TEXT_TO_IMAGE,
        params={
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": width,
            "height": height,
            "n": request.n,
            "steps": request.steps,
            "guidance_scale": request.guidance_scale,
            "seed": request.seed,
        },
    )

    # Wait for task completion (with timeout)
    import time

    timeout = 300  # 5 minutes
    start_time = time.time()

    while time.time() - start_time < timeout:
        task = task_queue.get_task(task.id)
        if task.status.value in ["completed", "failed", "cancelled"]:
            break
        await asyncio.sleep(0.5)

    if task.status.value == "failed":
        raise HTTPException(status_code=500, detail=task.error or "Generation failed")

    if task.status.value == "cancelled":
        raise HTTPException(status_code=400, detail="Task was cancelled")

    if task.status.value != "completed":
        raise HTTPException(status_code=504, detail="Generation timeout")

    # Build response
    result = task.result
    data = []

    for image_path in result.get("images", []):
        if request.response_format == "b64_json":
            b64 = image_to_base64(image_path)
            data.append(ImageData(b64_json=b64, revised_prompt=request.prompt))
        else:
            # Return relative URL
            filename = os.path.basename(image_path)
            data.append(
                ImageData(url=f"/v1/images/files/{filename}", revised_prompt=request.prompt)
            )

    return ImageGenerationResponse(created=int(time.time()), data=data)


@router.post("/v1/images/edits", response_model=ImageGenerationResponse)
async def edit_image(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    model: str = Form(default="stable-diffusion-3.5-medium"),
    n: int = Form(default=1),
    size: str = Form(default="1024x1024"),
    response_format: str = Form(default="url"),
    strength: float = Form(default=0.8),
    steps: int = Form(default=28),
    guidance_scale: float = Form(default=3.5),
    seed: Optional[int] = Form(default=None),
):
    """
    Edit/transform an image based on a prompt.

    OpenAI compatible endpoint for image-to-image generation.
    """
    instance = get_model_instance()
    if not instance or not instance.is_loaded():
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Read and process image
    image_bytes = await image.read()
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Create task for queue
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = task_queue.add_task(
        TaskType.IMAGE_TO_IMAGE,
        params={
            "prompt": prompt,
            "image": pil_image,
            "strength": strength,
            "n": n,
            "steps": steps,
            "guidance_scale": guidance_scale,
            "seed": seed,
        },
    )

    # Wait for task completion
    import time

    timeout = 300
    start_time = time.time()

    while time.time() - start_time < timeout:
        task = task_queue.get_task(task.id)
        if task.status.value in ["completed", "failed", "cancelled"]:
            break
        await asyncio.sleep(0.5)

    if task.status.value == "failed":
        raise HTTPException(status_code=500, detail=task.error or "Generation failed")

    if task.status.value != "completed":
        raise HTTPException(status_code=504, detail="Generation timeout")

    # Build response
    result = task.result
    data = []

    for image_path in result.get("images", []):
        if response_format == "b64_json":
            b64 = image_to_base64(image_path)
            data.append(ImageData(b64_json=b64, revised_prompt=prompt))
        else:
            filename = os.path.basename(image_path)
            data.append(ImageData(url=f"/v1/images/files/{filename}", revised_prompt=prompt))

    return ImageGenerationResponse(created=int(time.time()), data=data)


@router.post("/v1/images/variations", response_model=ImageGenerationResponse)
async def create_image_variation(
    image: UploadFile = File(...),
    model: str = Form(default="stable-diffusion-3.5-medium"),
    n: int = Form(default=1),
    size: str = Form(default="1024x1024"),
    response_format: str = Form(default="url"),
):
    """
    Create variations of an image.

    OpenAI compatible endpoint for image variations.
    """
    # For variations, we use img2img with generic prompt
    return await edit_image(
        image=image,
        prompt="Create a variation of this image while maintaining the overall style and composition",
        model=model,
        n=n,
        size=size,
        response_format=response_format,
        strength=0.6,  # Lower strength for variations
    )


@router.get("/v1/images/files/{filename}")
async def get_image_file(filename: str):
    """Serve generated image files."""
    instance = get_model_instance()
    if not instance:
        raise HTTPException(status_code=503, detail="Service not initialized")

    filepath = os.path.join(instance._config.output_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(filepath, media_type="image/png")


# ============================================================================
# Queue Endpoints
# ============================================================================


@router.get("/v1/queue")
async def get_queue_status():
    """Get current queue status."""
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    return task_queue.get_queue_status()


@router.get("/v1/queue/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return task.to_dict()


@router.get("/v1/queue/{task_id}/result")
async def get_task_result(task_id: str):
    """Get result of a completed task."""
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status.value != "completed":
        raise HTTPException(
            status_code=400, detail=f"Task not completed. Status: {task.status.value}"
        )

    return {"task_id": task_id, "result": task.result}


@router.delete("/v1/queue/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending task."""
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    success = task_queue.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400, detail="Cannot cancel task (not pending or not found)"
        )

    return {"status": "cancelled", "task_id": task_id}


@router.delete("/v1/queue")
async def clear_queue():
    """Clear all pending tasks."""
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    count = task_queue.clear_queue()
    return {"status": "cleared", "cancelled_count": count}


@router.get("/v1/queue/history")
async def get_queue_history(limit: int = 50):
    """Get task history."""
    task_queue = get_task_queue()
    if not task_queue:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    return {"history": task_queue.get_history(limit)}
