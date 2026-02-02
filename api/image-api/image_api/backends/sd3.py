"""Stable Diffusion 3.5 backend implementation."""

import gc
import logging
import os
from typing import Optional, Union

import torch
from PIL import Image

from .base import GenerationResult, ImageBackend


logger = logging.getLogger(__name__)


class StableDiffusion3Backend(ImageBackend):
    """Stable Diffusion 3.5 backend using diffusers."""

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        dtype: str = "float16",
        enable_quantization: bool = True,
    ):
        super().__init__(model_path, device, dtype)
        self.enable_quantization = enable_quantization
        self._txt2img_pipeline = None
        self._img2img_pipeline = None

    def load(self) -> None:
        """Load the Stable Diffusion 3.5 model."""
        if self._is_loaded:
            logger.warning("Model already loaded")
            return

        logger.info(f"Loading Stable Diffusion 3.5 model from {self.model_path}")

        try:
            from diffusers import (
                StableDiffusion3Pipeline,
                StableDiffusion3Img2ImgPipeline,
            )

            # Determine dtype
            torch_dtype = torch.float16 if self.dtype == "float16" else torch.float32

            # Check VRAM and decide on quantization strategy
            # 8G VRAM: int4 quantization
            # 12G VRAM: 8bit quantization
            # 24G+ VRAM: fp16 (no quantization)
            total_vram = self.get_total_vram()
            quantization_mode = self._determine_quantization_mode(total_vram)

            logger.info(
                f"Total VRAM: {total_vram:.1f}GB, Quantization mode: {quantization_mode}"
            )

            # Load pipeline based on quantization mode
            if quantization_mode == "int4" and self._is_bitsandbytes_available():
                logger.info("Loading model with INT4 quantization (8G VRAM)")
                self._txt2img_pipeline = self._load_quantized_pipeline(
                    StableDiffusion3Pipeline, torch_dtype, load_in_4bit=True
                )
            elif quantization_mode == "int8" and self._is_bitsandbytes_available():
                logger.info("Loading model with INT8 quantization (12G VRAM)")
                self._txt2img_pipeline = self._load_quantized_pipeline(
                    StableDiffusion3Pipeline, torch_dtype, load_in_4bit=False
                )
            else:
                logger.info("Loading model in FP16 precision (24G+ VRAM)")
                self._txt2img_pipeline = StableDiffusion3Pipeline.from_pretrained(
                    self.model_path,
                    torch_dtype=torch_dtype,
                    local_files_only=True,
                )
                self._txt2img_pipeline.to(self.device)

            # Enable memory optimizations
            self._txt2img_pipeline.enable_attention_slicing()

            # Enable CPU offload for very low VRAM
            if hasattr(self._txt2img_pipeline, "enable_model_cpu_offload"):
                if total_vram < 10:
                    logger.info("Enabling CPU offload due to low VRAM")
                    self._txt2img_pipeline.enable_model_cpu_offload()

            # Create img2img pipeline sharing components
            self._img2img_pipeline = StableDiffusion3Img2ImgPipeline(
                transformer=self._txt2img_pipeline.transformer,
                scheduler=self._txt2img_pipeline.scheduler,
                vae=self._txt2img_pipeline.vae,
                text_encoder=self._txt2img_pipeline.text_encoder,
                tokenizer=self._txt2img_pipeline.tokenizer,
                text_encoder_2=self._txt2img_pipeline.text_encoder_2,
                tokenizer_2=self._txt2img_pipeline.tokenizer_2,
                text_encoder_3=self._txt2img_pipeline.text_encoder_3,
                tokenizer_3=self._txt2img_pipeline.tokenizer_3,
            )

            self._is_loaded = True
            logger.info("Model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _determine_quantization_mode(self, total_vram: float) -> str:
        """
        Determine quantization mode based on available VRAM.

        - 8G VRAM: int4 quantization
        - 12G VRAM: int8 quantization
        - 24G+ VRAM: fp16 (no quantization)
        """
        if not self.enable_quantization:
            return "none"

        if total_vram < 10:  # ~8G
            return "int4"
        elif total_vram < 20:  # ~12G
            return "int8"
        else:  # 24G+
            return "none"

    def _is_bitsandbytes_available(self) -> bool:
        """Check if bitsandbytes is available for quantization."""
        try:
            import bitsandbytes
            return True
        except ImportError:
            return False

    def _load_quantized_pipeline(self, pipeline_class, torch_dtype, load_in_4bit: bool = False):
        """
        Load pipeline with quantization.

        Args:
            pipeline_class: The diffusers pipeline class
            torch_dtype: Torch data type
            load_in_4bit: If True, use INT4; otherwise use INT8
        """
        from diffusers import BitsAndBytesConfig

        if load_in_4bit:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch_dtype,
            )
        else:
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
            )

        pipeline = pipeline_class.from_pretrained(
            self.model_path,
            torch_dtype=torch_dtype,
            quantization_config=quantization_config,
            local_files_only=True,
        )
        return pipeline

    def unload(self) -> None:
        """Unload the model from memory."""
        if self._txt2img_pipeline:
            del self._txt2img_pipeline
            self._txt2img_pipeline = None

        if self._img2img_pipeline:
            del self._img2img_pipeline
            self._img2img_pipeline = None

        self._is_loaded = False

        # Force garbage collection
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("Model unloaded")

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
        """Generate images from text prompt."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        logger.info(f"Generating {num_images} image(s) for prompt: {prompt[:50]}...")

        # Set seed for reproducibility
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        else:
            seed = torch.randint(0, 2**32 - 1, (1,)).item()
            generator = torch.Generator(device=self.device).manual_seed(seed)

        try:
            output = self._txt2img_pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_images_per_prompt=num_images,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )

            return GenerationResult(
                images=output.images,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=num_inference_steps,
                guidance_scale=guidance_scale,
                width=width,
                height=height,
                model=os.path.basename(self.model_path),
            )

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise

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
        """Generate images based on input image and prompt."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Load image if path provided
        if isinstance(image, str):
            image = Image.open(image).convert("RGB")

        logger.info(
            f"Generating {num_images} image(s) from input image with prompt: {prompt[:50]}..."
        )

        # Set seed for reproducibility
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        else:
            seed = torch.randint(0, 2**32 - 1, (1,)).item()
            generator = torch.Generator(device=self.device).manual_seed(seed)

        try:
            output = self._img2img_pipeline(
                prompt=prompt,
                image=image,
                negative_prompt=negative_prompt,
                strength=strength,
                num_images_per_prompt=num_images,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator,
            )

            return GenerationResult(
                images=output.images,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=num_inference_steps,
                guidance_scale=guidance_scale,
                width=output.images[0].width,
                height=output.images[0].height,
                model=os.path.basename(self.model_path),
            )

        except Exception as e:
            logger.error(f"Image-to-image generation failed: {e}")
            raise

    def model_info(self) -> dict:
        """Get information about the loaded model."""
        info = super().model_info()
        info.update(
            {
                "backend": "stable_diffusion_3",
                "quantization_enabled": self.enable_quantization,
                "vram_total_gb": round(self.get_total_vram(), 1),
                "vram_available_gb": round(self.get_available_vram(), 1),
            }
        )
        return info
