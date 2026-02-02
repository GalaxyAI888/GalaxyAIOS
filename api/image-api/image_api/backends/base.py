"""Base class for image generation backends."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Union
from PIL import Image


logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of image generation."""

    images: List[Image.Image]
    prompt: str
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    steps: int = 0
    guidance_scale: float = 0.0
    width: int = 0
    height: int = 0
    model: str = ""


class ImageBackend(ABC):
    """Abstract base class for image generation backends."""

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        dtype: str = "float16",
    ):
        self.model_path = model_path
        self.device = device
        self.dtype = dtype
        self._is_loaded = False
        self._pipeline = None

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._is_loaded

    @abstractmethod
    def load(self) -> None:
        """Load the model into memory."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Unload the model from memory."""
        pass

    @abstractmethod
    def text_to_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        seed: Optional[int] = None,
    ) -> GenerationResult:
        """
        Generate images from text prompt.

        Args:
            prompt: Text description of the image
            negative_prompt: Text to avoid in the image
            width: Image width
            height: Image height
            num_images: Number of images to generate
            num_inference_steps: Number of denoising steps
            guidance_scale: Guidance scale for generation
            seed: Random seed for reproducibility

        Returns:
            GenerationResult with generated images
        """
        pass

    @abstractmethod
    def image_to_image(
        self,
        prompt: str,
        image: Union[Image.Image, str],
        negative_prompt: Optional[str] = None,
        strength: float = 0.8,
        num_images: int = 1,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        seed: Optional[int] = None,
    ) -> GenerationResult:
        """
        Generate images based on input image and prompt.

        Args:
            prompt: Text description of the desired output
            image: Input image or path to image
            negative_prompt: Text to avoid
            strength: How much to transform the image (0-1)
            num_images: Number of images to generate
            num_inference_steps: Number of denoising steps
            guidance_scale: Guidance scale
            seed: Random seed

        Returns:
            GenerationResult with generated images
        """
        pass

    def model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "id": self.model_path,
            "object": "model",
            "owned_by": "image-api",
            "loaded": self._is_loaded,
            "device": self.device,
            "dtype": self.dtype,
        }

    @staticmethod
    def get_available_vram() -> float:
        """Get available VRAM in GB."""
        try:
            import torch

            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                total = torch.cuda.get_device_properties(device).total_memory
                allocated = torch.cuda.memory_allocated(device)
                return (total - allocated) / (1024**3)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def get_total_vram() -> float:
        """Get total VRAM in GB."""
        try:
            import torch

            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                total = torch.cuda.get_device_properties(device).total_memory
                return total / (1024**3)
        except Exception:
            pass
        return 0.0
