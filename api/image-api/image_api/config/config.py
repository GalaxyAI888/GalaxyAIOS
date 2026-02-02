"""Configuration classes for Image API."""

from typing import Optional


class Config:
    """Configuration class for Image API server.

    Attributes:
        debug: Enable debug mode.
        host: Host to bind the server to.
        port: Port to bind the server to.
        device: CUDA device to use (e.g., cuda:0).
        model_dir: Directory to store model files.
        output_dir: Directory to store output images.
        logs_dir: Directory to store log files.
        huggingface_repo_id: HuggingFace repo id for the model.
        model_scope_model_id: ModelScope model id for the model.
    """

    # Common options
    debug: bool = False

    # Server options
    host: str = "0.0.0.0"
    port: int = 80

    # Device options
    device: str = "cuda:0"

    # Directory options
    model_dir: Optional[str] = None
    output_dir: Optional[str] = None
    logs_dir: Optional[str] = None
    cache_dir: Optional[str] = None

    # Model options
    huggingface_repo_id: Optional[str] = None
    model_scope_model_id: Optional[str] = None

    def __init__(self):
        pass

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "debug": self.debug,
            "host": self.host,
            "port": self.port,
            "device": self.device,
            "model_dir": self.model_dir,
            "output_dir": self.output_dir,
            "logs_dir": self.logs_dir,
            "cache_dir": self.cache_dir,
            "huggingface_repo_id": self.huggingface_repo_id,
            "model_scope_model_id": self.model_scope_model_id,
        }
