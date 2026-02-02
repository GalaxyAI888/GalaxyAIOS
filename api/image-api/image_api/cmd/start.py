"""Start command for Image API server."""

import argparse
import asyncio
import logging
import os

from image_api.logging import setup_logging
from image_api.config import Config
from image_api.server.server import Server
from image_api.server.model import ModelInstance


logger = logging.getLogger(__name__)


class OptionalBoolAction(argparse.Action):
    """Custom action for optional boolean arguments."""

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(OptionalBoolAction, self).__init__(
            option_strings, dest, nargs=0, **kwargs
        )
        self.default = None

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, True)


def setup_start_cmd(subparsers: argparse._SubParsersAction):
    """Setup the start command parser."""
    parser_server: argparse.ArgumentParser = subparsers.add_parser(
        "start",
        help="Run image-api server.",
        description="Run image-api server for text-to-image and image-to-image generation.",
    )

    # Common settings
    group = parser_server.add_argument_group("Common settings")
    group.add_argument(
        "-d",
        "--debug",
        action=OptionalBoolAction,
        help="Enable debug mode.",
        default=False,
    )

    # Server settings
    group = parser_server.add_argument_group("Server settings")
    group.add_argument(
        "--host",
        type=str,
        help="Host to bind the server to.",
        default="0.0.0.0",
    )
    group.add_argument(
        "--port",
        type=int,
        help="Port to bind the server to.",
        default=80,
    )
    group.add_argument(
        "--device",
        type=str,
        help="Binding device, e.g., cuda:0.",
        default="cuda:0",
    )

    # Model settings
    group = parser_server.add_argument_group("Model settings")
    group.add_argument(
        "--huggingface-repo-id",
        type=str,
        help="HuggingFace repo id for the model.",
    )
    group.add_argument(
        "--model-scope-model-id",
        type=str,
        help="ModelScope model id for the model.",
    )

    # Directory settings
    group = parser_server.add_argument_group("Directory settings")
    group.add_argument(
        "--model-dir",
        type=str,
        help="Directory to store model files.",
    )
    group.add_argument(
        "--output-dir",
        type=str,
        help="Directory to store output images.",
    )
    group.add_argument(
        "--logs-dir",
        type=str,
        help="Directory to store log files.",
    )

    parser_server.set_defaults(func=run)


def run(args: argparse.Namespace):
    """Run the Image API server."""
    try:
        cfg = parse_args(args)
        setup_logging(cfg.debug, cfg.logs_dir)

        logger.info("Starting Image API with arguments: %s", args._get_kwargs())

        # Initialize and run model instance
        model_instance = ModelInstance(cfg)
        model_instance.run()

        # Start server
        run_server(cfg)
    except Exception as e:
        logger.fatal("Failed to start server: %s", e)
        raise


def run_server(cfg: Config):
    """Start the FastAPI server."""
    server = Server(config=cfg)
    asyncio.run(server.start())


def parse_args(args: argparse.Namespace) -> Config:
    """Parse command line arguments into Config object."""
    validate_args(args)

    cfg = Config()
    cfg.debug = args.debug or False
    cfg.host = args.host
    cfg.port = args.port
    cfg.device = args.device

    cfg.huggingface_repo_id = args.huggingface_repo_id
    cfg.model_scope_model_id = args.model_scope_model_id

    cfg.model_dir = args.model_dir or get_default_model_dir()
    cfg.output_dir = args.output_dir or get_default_output_dir()
    cfg.logs_dir = args.logs_dir or get_default_logs_dir()
    cfg.cache_dir = os.path.join(cfg.model_dir, ".cache")

    # Create directories
    os.makedirs(cfg.model_dir, exist_ok=True)
    os.makedirs(cfg.output_dir, exist_ok=True)
    os.makedirs(cfg.logs_dir, exist_ok=True)
    os.makedirs(cfg.cache_dir, exist_ok=True)

    return cfg


def validate_args(args: argparse.Namespace):
    """Validate command line arguments."""
    if args.huggingface_repo_id is None and args.model_scope_model_id is None:
        raise ValueError(
            "One of --huggingface-repo-id or --model-scope-model-id is required."
        )


def get_default_model_dir() -> str:
    """Get default model directory based on OS."""
    app_name = "image-api"
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, app_name, "models")
    else:  # Linux/macOS
        return f"/var/lib/{app_name}/models"


def get_default_output_dir() -> str:
    """Get default output directory based on OS."""
    app_name = "image-api"
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, app_name, "output")
    else:  # Linux/macOS
        return f"/var/lib/{app_name}/output"


def get_default_logs_dir() -> str:
    """Get default logs directory based on OS."""
    app_name = "image-api"
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, app_name, "logs")
    else:  # Linux/macOS
        return f"/var/log/{app_name}"
