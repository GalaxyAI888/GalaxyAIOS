"""GPU utility functions."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def is_cuda_available() -> bool:
    """Check if CUDA is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def get_vram_gb(device_id: int = 0) -> float:
    """
    Get total VRAM in GB for specified device.

    Args:
        device_id: CUDA device ID

    Returns:
        Total VRAM in GB, 0 if not available
    """
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(device_id)
            return props.total_memory / (1024 ** 3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM info: {e}")
    return 0.0


def get_gpu_info(device_id: int = 0) -> Dict:
    """
    Get detailed GPU information.

    Args:
        device_id: CUDA device ID

    Returns:
        Dictionary with GPU info
    """
    info = {
        "available": False,
        "device_id": device_id,
        "name": "N/A",
        "total_memory_gb": 0.0,
        "allocated_memory_gb": 0.0,
        "free_memory_gb": 0.0,
        "compute_capability": "N/A",
    }

    try:
        import torch
        if not torch.cuda.is_available():
            return info

        info["available"] = True
        props = torch.cuda.get_device_properties(device_id)

        info["name"] = props.name
        info["total_memory_gb"] = round(props.total_memory / (1024 ** 3), 2)
        info["compute_capability"] = f"{props.major}.{props.minor}"

        allocated = torch.cuda.memory_allocated(device_id)
        info["allocated_memory_gb"] = round(allocated / (1024 ** 3), 2)
        info["free_memory_gb"] = round(
            (props.total_memory - allocated) / (1024 ** 3), 2
        )

    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")

    return info


def get_quantization_recommendation(vram_gb: float) -> str:
    """
    Get quantization recommendation based on VRAM.

    Args:
        vram_gb: Available VRAM in GB

    Returns:
        Recommended quantization mode: 'int4', 'int8', or 'fp16'
    """
    if vram_gb < 10:
        return "int4"
    elif vram_gb < 20:
        return "int8"
    else:
        return "fp16"
