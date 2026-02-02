"""Model downloader from HuggingFace and ModelScope."""

import logging
import os
import threading
from typing import Callable, Optional

from huggingface_hub import snapshot_download as hf_snapshot_download
from huggingface_hub.utils import validate_repo_id

from image_api.models.status import ModelStatus, get_status_manager


logger = logging.getLogger(__name__)


class DownloadProgressCallback:
    """Callback for tracking download progress."""

    def __init__(self, model_name: str, on_progress: Optional[Callable[[float], None]] = None):
        self.model_name = model_name
        self.on_progress = on_progress
        self._total_files = 0
        self._completed_files = 0

    def __call__(self, progress: float):
        """Called when progress updates."""
        if self.on_progress:
            self.on_progress(progress)

        status_manager = get_status_manager()
        if status_manager:
            status_manager.update_progress(self.model_name, progress)


class ModelDownloader:
    """Download models from HuggingFace or ModelScope."""

    def __init__(
        self,
        model_dir: str,
        huggingface_repo_id: Optional[str] = None,
        model_scope_model_id: Optional[str] = None,
    ):
        self.model_dir = model_dir
        self.huggingface_repo_id = huggingface_repo_id
        self.model_scope_model_id = model_scope_model_id
        self._download_thread: Optional[threading.Thread] = None
        self._is_downloading = False

    def get_model_name(self) -> str:
        """Get model name from repo/model id."""
        if self.huggingface_repo_id:
            return self.huggingface_repo_id.split("/")[-1]
        elif self.model_scope_model_id:
            return self.model_scope_model_id.split("/")[-1]
        return "unknown"

    def get_local_path(self) -> str:
        """Get local path for the model."""
        model_name = self.get_model_name()
        return os.path.join(self.model_dir, model_name)

    def is_downloaded(self) -> bool:
        """Check if model is already downloaded."""
        local_path = self.get_local_path()
        if not os.path.exists(local_path):
            return False

        # Check if directory has content
        if not os.listdir(local_path):
            return False

        # Check for essential files (model_index.json for diffusers models)
        model_index = os.path.join(local_path, "model_index.json")
        return os.path.exists(model_index)

    def download(
        self,
        on_progress: Optional[Callable[[float], None]] = None,
        force: bool = False,
    ) -> str:
        """
        Download model synchronously.

        Args:
            on_progress: Callback for progress updates (0-100)
            force: Force re-download even if exists

        Returns:
            Path to downloaded model
        """
        model_name = self.get_model_name()
        local_path = self.get_local_path()

        if not force and self.is_downloaded():
            logger.info(f"Model {model_name} already downloaded at {local_path}")
            return local_path

        status_manager = get_status_manager()
        if status_manager:
            status_manager.set_status(model_name, ModelStatus.DOWNLOADING, progress=0)

        try:
            os.makedirs(local_path, exist_ok=True)

            if self.huggingface_repo_id:
                self._download_from_huggingface(local_path, on_progress)
            elif self.model_scope_model_id:
                self._download_from_modelscope(local_path, on_progress)
            else:
                raise ValueError("No model source specified")

            if status_manager:
                status_manager.set_status(
                    model_name, ModelStatus.DOWNLOADED, progress=100
                )

            logger.info(f"Model {model_name} downloaded successfully to {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Failed to download model {model_name}: {e}")
            if status_manager:
                status_manager.set_status(
                    model_name, ModelStatus.FAILED, error_message=str(e)
                )
            raise

    def download_async(
        self,
        on_progress: Optional[Callable[[float], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        force: bool = False,
    ):
        """
        Download model asynchronously in background thread.

        Args:
            on_progress: Callback for progress updates (0-100)
            on_complete: Callback when download completes
            on_error: Callback when download fails
            force: Force re-download
        """
        if self._is_downloading:
            logger.warning("Download already in progress")
            return

        def download_task():
            self._is_downloading = True
            try:
                path = self.download(on_progress=on_progress, force=force)
                if on_complete:
                    on_complete(path)
            except Exception as e:
                if on_error:
                    on_error(e)
            finally:
                self._is_downloading = False

        self._download_thread = threading.Thread(target=download_task, daemon=True)
        self._download_thread.start()

    def _download_from_huggingface(
        self,
        local_path: str,
        on_progress: Optional[Callable[[float], None]] = None,
    ):
        """Download from HuggingFace Hub."""
        validate_repo_id(self.huggingface_repo_id)

        logger.info(f"Downloading from HuggingFace: {self.huggingface_repo_id}")

        # Use HF mirror if available
        endpoint = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")

        hf_snapshot_download(
            repo_id=self.huggingface_repo_id,
            local_dir=local_path,
            local_dir_use_symlinks=False,
            endpoint=endpoint,
        )

    def _download_from_modelscope(
        self,
        local_path: str,
        on_progress: Optional[Callable[[float], None]] = None,
    ):
        """Download from ModelScope."""
        from modelscope.hub.snapshot_download import snapshot_download as ms_snapshot_download

        logger.info(f"Downloading from ModelScope: {self.model_scope_model_id}")

        ms_snapshot_download(
            model_id=self.model_scope_model_id,
            local_dir=local_path,
        )


def download_model(
    model_dir: str,
    huggingface_repo_id: Optional[str] = None,
    model_scope_model_id: Optional[str] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    force: bool = False,
) -> str:
    """
    Convenience function to download a model.

    Args:
        model_dir: Directory to store models
        huggingface_repo_id: HuggingFace repo ID
        model_scope_model_id: ModelScope model ID
        on_progress: Progress callback
        force: Force re-download

    Returns:
        Path to downloaded model
    """
    downloader = ModelDownloader(
        model_dir=model_dir,
        huggingface_repo_id=huggingface_repo_id,
        model_scope_model_id=model_scope_model_id,
    )
    return downloader.download(on_progress=on_progress, force=force)
