"""Image utility functions."""

import base64
import io
import logging
import os
from typing import Optional, Union

from PIL import Image

logger = logging.getLogger(__name__)


def load_image(source: Union[str, bytes, io.BytesIO]) -> Image.Image:
    """
    Load an image from various sources.

    Args:
        source: File path, bytes, or BytesIO

    Returns:
        PIL Image object
    """
    if isinstance(source, str):
        if os.path.exists(source):
            return Image.open(source).convert("RGB")
        elif source.startswith("data:image"):
            # Handle data URL
            header, data = source.split(",", 1)
            return base64_to_image(data)
        else:
            raise ValueError(f"Invalid image source: {source}")
    elif isinstance(source, bytes):
        return Image.open(io.BytesIO(source)).convert("RGB")
    elif isinstance(source, io.BytesIO):
        return Image.open(source).convert("RGB")
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")


def save_image(
    image: Image.Image,
    path: str,
    format: Optional[str] = None,
    quality: int = 95,
) -> str:
    """
    Save an image to file.

    Args:
        image: PIL Image to save
        path: Output file path
        format: Image format (auto-detected from extension if None)
        quality: JPEG quality (1-100)

    Returns:
        Path to saved image
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    if format is None:
        ext = os.path.splitext(path)[1].lower()
        format_map = {
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".png": "PNG",
            ".webp": "WEBP",
            ".gif": "GIF",
        }
        format = format_map.get(ext, "PNG")

    save_kwargs = {}
    if format == "JPEG":
        save_kwargs["quality"] = quality
    elif format == "WEBP":
        save_kwargs["quality"] = quality

    image.save(path, format=format, **save_kwargs)
    logger.debug(f"Image saved to {path}")
    return path


def image_to_base64(image: Union[Image.Image, str], format: str = "PNG") -> str:
    """
    Convert image to base64 string.

    Args:
        image: PIL Image or file path
        format: Output format

    Returns:
        Base64 encoded string
    """
    if isinstance(image, str):
        with open(image, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def base64_to_image(b64_string: str) -> Image.Image:
    """
    Convert base64 string to PIL Image.

    Args:
        b64_string: Base64 encoded image string

    Returns:
        PIL Image object
    """
    image_data = base64.b64decode(b64_string)
    return Image.open(io.BytesIO(image_data)).convert("RGB")


def resize_image(
    image: Image.Image,
    width: Optional[int] = None,
    height: Optional[int] = None,
    max_size: Optional[int] = None,
    keep_aspect: bool = True,
) -> Image.Image:
    """
    Resize an image.

    Args:
        image: PIL Image to resize
        width: Target width
        height: Target height
        max_size: Maximum dimension (overrides width/height)
        keep_aspect: Maintain aspect ratio

    Returns:
        Resized image
    """
    orig_width, orig_height = image.size

    if max_size:
        # Resize based on max dimension
        if orig_width > orig_height:
            width = max_size
            height = int(max_size * orig_height / orig_width)
        else:
            height = max_size
            width = int(max_size * orig_width / orig_height)
    elif keep_aspect:
        if width and not height:
            height = int(width * orig_height / orig_width)
        elif height and not width:
            width = int(height * orig_width / orig_height)

    if width and height:
        return image.resize((width, height), Image.Resampling.LANCZOS)
    return image
