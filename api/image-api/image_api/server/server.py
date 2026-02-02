"""Server implementation for Image API."""

import logging

import uvicorn

from image_api.config import Config
from image_api.logging import setup_logging
from .app import app


logger = logging.getLogger(__name__)


class Server:
    """FastAPI server wrapper."""

    def __init__(self, config: Config):
        self._config = config

    @property
    def config(self) -> Config:
        """Get server configuration."""
        return self._config

    async def start(self):
        """Start the FastAPI server."""
        logger.info("Starting Image API server")

        host = self._config.host or "0.0.0.0"
        port = self._config.port or 80

        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            access_log=False,
            log_level="warning" if not self._config.debug else "debug",
        )

        # Setup logging again with logs_dir
        setup_logging(self._config.debug, self._config.logs_dir)

        logger.info(f"Server listening on {host}:{port}")
        logger.info(f"API documentation available at http://{host}:{port}/docs")

        server = uvicorn.Server(config)
        await server.serve()
