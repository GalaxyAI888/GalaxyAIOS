"""End-to-end tests for Image API."""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
import io

from fastapi.testclient import TestClient


# Mock torch before importing image_api modules
@pytest.fixture(autouse=True)
def mock_torch():
    """Mock torch for testing without GPU."""
    with patch.dict("sys.modules", {"torch": MagicMock()}):
        yield


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as model_dir:
        with tempfile.TemporaryDirectory() as output_dir:
            with tempfile.TemporaryDirectory() as logs_dir:
                yield {
                    "model_dir": model_dir,
                    "output_dir": output_dir,
                    "logs_dir": logs_dir,
                }


class TestModelRegistry:
    """Tests for model registry."""

    def test_list_models(self):
        """Test listing all models."""
        from image_api.models import MODEL_REGISTRY

        models = MODEL_REGISTRY.list_all()
        assert len(models) > 0

        # Check SD3.5 medium exists
        names = MODEL_REGISTRY.list_names()
        assert "stable-diffusion-3.5-medium" in names

    def test_get_model_by_name(self):
        """Test getting model by name."""
        from image_api.models import MODEL_REGISTRY

        model = MODEL_REGISTRY.get("stable-diffusion-3.5-medium")
        assert model is not None
        assert model.name == "stable-diffusion-3.5-medium"
        assert model.backend == "stable_diffusion_3"

    def test_get_model_by_modelscope(self):
        """Test getting model by ModelScope ID."""
        from image_api.models import MODEL_REGISTRY

        model = MODEL_REGISTRY.get_by_modelscope("AI-ModelScope/stable-diffusion-3.5-medium")
        assert model is not None
        assert model.name == "stable-diffusion-3.5-medium"

    def test_get_model_by_hf_repo(self):
        """Test getting model by HuggingFace repo."""
        from image_api.models import MODEL_REGISTRY

        model = MODEL_REGISTRY.get_by_hf_repo("stabilityai/stable-diffusion-3.5-medium")
        assert model is not None
        assert model.name == "stable-diffusion-3.5-medium"

    def test_model_to_dict(self):
        """Test model info serialization."""
        from image_api.models import MODEL_REGISTRY

        model = MODEL_REGISTRY.get("stable-diffusion-3.5-medium")
        info = model.to_dict()

        assert "name" in info
        assert "modelscope" in info
        assert "hf_repo" in info
        assert "components" in info


class TestModelStatus:
    """Tests for model status management."""

    def test_status_manager(self, temp_dirs):
        """Test status manager initialization."""
        from image_api.models import init_status_manager, ModelStatus

        manager = init_status_manager(temp_dirs["model_dir"])
        assert manager is not None

        # Get status for non-existent model
        status = manager.get_status("test-model")
        assert status.status == ModelStatus.NOT_DOWNLOADED

    def test_set_status(self, temp_dirs):
        """Test setting model status."""
        from image_api.models import init_status_manager, ModelStatus

        manager = init_status_manager(temp_dirs["model_dir"])

        manager.set_status("test-model", ModelStatus.DOWNLOADING, progress=50)
        status = manager.get_status("test-model")

        assert status.status == ModelStatus.DOWNLOADING
        assert status.progress == 50

    def test_status_to_dict(self, temp_dirs):
        """Test status serialization."""
        from image_api.models import init_status_manager, ModelStatus

        manager = init_status_manager(temp_dirs["model_dir"])
        manager.set_status("test-model", ModelStatus.ENABLED)

        status = manager.get_status("test-model")
        info = status.to_dict()

        assert "status" in info
        assert info["status"] == "enabled"


class TestTaskQueue:
    """Tests for task queue."""

    def test_queue_initialization(self):
        """Test queue initialization."""
        from image_api.queue import init_task_queue, TaskQueue

        queue = init_task_queue()
        assert queue is not None
        assert isinstance(queue, TaskQueue)

    def test_add_task(self):
        """Test adding task to queue."""
        from image_api.queue import init_task_queue, TaskType, TaskStatus

        queue = init_task_queue()
        task = queue.add_task(
            TaskType.TEXT_TO_IMAGE,
            params={"prompt": "test prompt"},
        )

        assert task is not None
        assert task.status == TaskStatus.PENDING
        assert task.position == 1

    def test_get_task(self):
        """Test getting task by ID."""
        from image_api.queue import init_task_queue, TaskType

        queue = init_task_queue()
        task = queue.add_task(
            TaskType.TEXT_TO_IMAGE,
            params={"prompt": "test"},
        )

        retrieved = queue.get_task(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id

    def test_cancel_task(self):
        """Test cancelling task."""
        from image_api.queue import init_task_queue, TaskType, TaskStatus

        queue = init_task_queue()
        task = queue.add_task(
            TaskType.TEXT_TO_IMAGE,
            params={"prompt": "test"},
        )

        success = queue.cancel_task(task.id)
        assert success

        task = queue.get_task(task.id)
        assert task.status == TaskStatus.CANCELLED

    def test_queue_status(self):
        """Test queue status."""
        from image_api.queue import init_task_queue, TaskType

        queue = init_task_queue()
        queue.add_task(TaskType.TEXT_TO_IMAGE, params={"prompt": "test1"})
        queue.add_task(TaskType.TEXT_TO_IMAGE, params={"prompt": "test2"})

        status = queue.get_queue_status()
        assert status["queue_length"] == 2
        assert len(status["pending_tasks"]) == 2

    def test_clear_queue(self):
        """Test clearing queue."""
        from image_api.queue import init_task_queue, TaskType

        queue = init_task_queue()
        queue.add_task(TaskType.TEXT_TO_IMAGE, params={"prompt": "test1"})
        queue.add_task(TaskType.TEXT_TO_IMAGE, params={"prompt": "test2"})

        count = queue.clear_queue()
        assert count == 2
        assert queue.get_pending_count() == 0


class TestConfig:
    """Tests for configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        from image_api.config import Config

        config = Config()
        assert config.host == "0.0.0.0"
        assert config.port == 80
        assert config.device == "cuda:0"
        assert config.debug is False

    def test_config_to_dict(self):
        """Test configuration serialization."""
        from image_api.config import Config

        config = Config()
        config.host = "localhost"
        config.port = 8882

        data = config.to_dict()
        assert data["host"] == "localhost"
        assert data["port"] == 8882


class TestAPIEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    def client(self, temp_dirs):
        """Create test client with mocked model instance."""
        from image_api.server.app import app
        from image_api.models import init_status_manager
        from image_api.queue import init_task_queue

        # Initialize managers
        init_status_manager(temp_dirs["model_dir"])
        init_task_queue()

        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert data["name"] == "Image API"

    def test_list_models_endpoint(self, client):
        """Test models list endpoint."""
        response = client.get("/v1/models")
        assert response.status_code == 200

        data = response.json()
        assert "object" in data
        assert data["object"] == "list"
        assert "data" in data
        assert len(data["data"]) > 0

    def test_get_model_endpoint(self, client):
        """Test get model endpoint."""
        response = client.get("/v1/models/stable-diffusion-3.5-medium")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert data["name"] == "stable-diffusion-3.5-medium"

    def test_get_model_not_found(self, client):
        """Test get model not found."""
        response = client.get("/v1/models/non-existent-model")
        assert response.status_code == 404

    def test_queue_status_endpoint(self, client):
        """Test queue status endpoint."""
        response = client.get("/v1/queue")
        assert response.status_code == 200

        data = response.json()
        assert "queue_length" in data
        assert "pending_tasks" in data

    def test_queue_history_endpoint(self, client):
        """Test queue history endpoint."""
        response = client.get("/v1/queue/history")
        assert response.status_code == 200

        data = response.json()
        assert "history" in data


class TestDownloader:
    """Tests for model downloader."""

    def test_downloader_initialization(self, temp_dirs):
        """Test downloader initialization."""
        from image_api.downloader import ModelDownloader

        downloader = ModelDownloader(
            model_dir=temp_dirs["model_dir"],
            model_scope_model_id="AI-ModelScope/stable-diffusion-3.5-medium",
        )

        assert downloader is not None
        assert downloader.get_model_name() == "stable-diffusion-3.5-medium"

    def test_get_local_path(self, temp_dirs):
        """Test getting local path."""
        from image_api.downloader import ModelDownloader

        downloader = ModelDownloader(
            model_dir=temp_dirs["model_dir"],
            huggingface_repo_id="stabilityai/stable-diffusion-3.5-medium",
        )

        path = downloader.get_local_path()
        assert temp_dirs["model_dir"] in path
        assert "stable-diffusion-3.5-medium" in path

    def test_is_downloaded_false(self, temp_dirs):
        """Test is_downloaded returns False for non-existent model."""
        from image_api.downloader import ModelDownloader

        downloader = ModelDownloader(
            model_dir=temp_dirs["model_dir"],
            model_scope_model_id="AI-ModelScope/stable-diffusion-3.5-medium",
        )

        assert downloader.is_downloaded() is False


class TestBackend:
    """Tests for image generation backends."""

    def test_generation_result(self):
        """Test generation result dataclass."""
        from image_api.backends.base import GenerationResult

        # Create dummy image
        img = Image.new("RGB", (512, 512), color="red")

        result = GenerationResult(
            images=[img],
            prompt="test prompt",
            seed=12345,
            steps=28,
            guidance_scale=3.5,
            width=512,
            height=512,
            model="test-model",
        )

        assert len(result.images) == 1
        assert result.prompt == "test prompt"
        assert result.seed == 12345


class TestIntegration:
    """Integration tests."""

    def test_full_queue_workflow(self, temp_dirs):
        """Test full queue workflow."""
        from image_api.queue import init_task_queue, TaskType, TaskStatus

        queue = init_task_queue()

        # Add multiple tasks
        tasks = []
        for i in range(3):
            task = queue.add_task(
                TaskType.TEXT_TO_IMAGE,
                params={"prompt": f"test prompt {i}"},
            )
            tasks.append(task)

        # Check positions
        assert tasks[0].position == 1
        assert tasks[1].position == 2
        assert tasks[2].position == 3

        # Cancel middle task
        queue.cancel_task(tasks[1].id)

        # Check status
        status = queue.get_queue_status()
        assert status["queue_length"] == 2

    def test_model_registry_with_status(self, temp_dirs):
        """Test model registry with status manager."""
        from image_api.models import MODEL_REGISTRY, init_status_manager, ModelStatus

        manager = init_status_manager(temp_dirs["model_dir"])

        # Get all models and set status
        for model in MODEL_REGISTRY.list_all():
            manager.set_status(model.name, ModelStatus.NOT_DOWNLOADED)

        # Check status
        status = manager.get_status("stable-diffusion-3.5-medium")
        assert status.status == ModelStatus.NOT_DOWNLOADED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
