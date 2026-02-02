"""Model instance management for Image API."""

import logging
import os
from typing import Optional

from image_api.backends import ImageBackend, StableDiffusion3Backend
from image_api.config import Config
from image_api.downloader import ModelDownloader
from image_api.models import MODEL_REGISTRY, ModelStatus, init_status_manager
from image_api.queue import init_task_queue, Task


logger = logging.getLogger(__name__)

# Global model instance
_model_instance: Optional["ModelInstance"] = None


def get_model_instance() -> Optional["ModelInstance"]:
    """Get the global model instance."""
    return _model_instance


class ModelInstance:
    """Manages the model instance lifecycle."""

    def __init__(self, config: Config):
        global _model_instance
        self._config = config
        self._backend: Optional[ImageBackend] = None
        self._model_name: Optional[str] = None
        self._model_path: Optional[str] = None

        # Initialize status manager
        init_status_manager(config.model_dir)

        # Initialize task queue
        self._task_queue = init_task_queue()
        self._task_queue.set_task_handler(self._handle_task)

        _model_instance = self

    @property
    def backend(self) -> Optional[ImageBackend]:
        """Get the current backend."""
        return self._backend

    @property
    def model_name(self) -> Optional[str]:
        """Get the current model name."""
        return self._model_name

    def run(self):
        """Initialize and load the model."""
        # Determine model info from repo/model id
        model_info = None
        if self._config.huggingface_repo_id:
            model_info = MODEL_REGISTRY.get_by_hf_repo(self._config.huggingface_repo_id)
        elif self._config.model_scope_model_id:
            model_info = MODEL_REGISTRY.get_by_modelscope(
                self._config.model_scope_model_id
            )

        if model_info:
            self._model_name = model_info.name
        else:
            # Use last part of repo id as model name
            if self._config.huggingface_repo_id:
                self._model_name = self._config.huggingface_repo_id.split("/")[-1]
            elif self._config.model_scope_model_id:
                self._model_name = self._config.model_scope_model_id.split("/")[-1]

        logger.info(f"Initializing model: {self._model_name}")

        # Download model if needed
        self._download_model_if_needed()

        # Create and load backend
        self._create_backend()

        if self._backend:
            self._backend.load()

        # Start task queue
        self._task_queue.start()

        logger.info(f"Model {self._model_name} ready for inference")

    def _download_model_if_needed(self):
        """Download model if not already present."""
        downloader = ModelDownloader(
            model_dir=self._config.model_dir,
            huggingface_repo_id=self._config.huggingface_repo_id,
            model_scope_model_id=self._config.model_scope_model_id,
        )

        if not downloader.is_downloaded():
            logger.info(f"Model not found, downloading {self._model_name}...")
            self._model_path = downloader.download()
        else:
            self._model_path = downloader.get_local_path()
            logger.info(f"Model found at {self._model_path}")

    def _create_backend(self):
        """Create the appropriate backend for the model."""
        if not self._model_path:
            raise ValueError("Model path not set")

        # Determine backend type
        model_info = MODEL_REGISTRY.get(self._model_name)
        backend_type = model_info.backend if model_info else "stable_diffusion_3"

        logger.info(f"Creating backend: {backend_type}")

        if backend_type in ["stable_diffusion_3", "stable_diffusion"]:
            self._backend = StableDiffusion3Backend(
                model_path=self._model_path,
                device=self._config.device,
            )
        else:
            # Default to SD3 backend
            logger.warning(
                f"Unknown backend type {backend_type}, using stable_diffusion_3"
            )
            self._backend = StableDiffusion3Backend(
                model_path=self._model_path,
                device=self._config.device,
            )

    def _handle_task(self, task: Task) -> dict:
        """Handle a task from the queue."""
        from image_api.queue import TaskType

        if not self._backend or not self._backend.is_loaded:
            raise RuntimeError("Backend not loaded")

        params = task.params

        if task.type == TaskType.TEXT_TO_IMAGE:
            result = self._backend.text_to_image(
                prompt=params.get("prompt", ""),
                negative_prompt=params.get("negative_prompt"),
                width=params.get("width", 1024),
                height=params.get("height", 1024),
                num_images=params.get("n", 1),
                num_inference_steps=params.get("steps", 28),
                guidance_scale=params.get("guidance_scale", 3.5),
                seed=params.get("seed"),
            )
        elif task.type == TaskType.IMAGE_TO_IMAGE:
            result = self._backend.image_to_image(
                prompt=params.get("prompt", ""),
                image=params.get("image"),
                negative_prompt=params.get("negative_prompt"),
                strength=params.get("strength", 0.8),
                num_images=params.get("n", 1),
                num_inference_steps=params.get("steps", 28),
                guidance_scale=params.get("guidance_scale", 3.5),
                seed=params.get("seed"),
            )
        else:
            raise ValueError(f"Unknown task type: {task.type}")

        # Save images and return paths
        output_paths = self._save_images(result, task.id)

        return {
            "images": output_paths,
            "seed": result.seed,
            "model": result.model,
        }

    def _save_images(self, result, task_id: str) -> list:
        """Save generated images to output directory."""
        import uuid
        from datetime import datetime

        output_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for i, image in enumerate(result.images):
            filename = f"{timestamp}_{task_id}_{i}.png"
            filepath = os.path.join(self._config.output_dir, filename)
            image.save(filepath)
            output_paths.append(filepath)
            logger.debug(f"Saved image to {filepath}")

        return output_paths

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._backend is not None and self._backend.is_loaded

    def model_info(self) -> dict:
        """Get model information."""
        info = {
            "id": self._model_name,
            "object": "model",
            "owned_by": "image-api",
        }

        if self._backend:
            info.update(self._backend.model_info())

        return info

    def shutdown(self):
        """Shutdown the model instance."""
        if self._task_queue:
            self._task_queue.stop()

        if self._backend:
            self._backend.unload()

        logger.info("Model instance shutdown complete")
