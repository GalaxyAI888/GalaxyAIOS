"""Logging configuration for Image API with rotating file handler."""

import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(
    debug: bool = False,
    logs_dir: Optional[str] = None,
    max_bytes: int = 20 * 1024 * 1024,  # 20MB
    backup_count: int = 4,  # Keep 5 files total (current + 4 backups)
):
    """
    Setup logging with console and rotating file handlers.

    Args:
        debug: Enable debug mode
        logs_dir: Directory to store log files
        max_bytes: Maximum size of each log file (default 20MB)
        backup_count: Number of backup files to keep (default 4)
    """
    level = logging.DEBUG if debug else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Custom time formatter for UTC
    logging.Formatter.formatTime = (
        lambda self, record, datefmt=None: datetime.fromtimestamp(
            record.created, timezone.utc
        )
        .astimezone()
        .isoformat(timespec="seconds")
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if logs_dir is specified)
    if logs_dir:
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, "image-api.log")

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Suppress verbose loggers from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("diffusers").setLevel(logging.INFO)
    logging.getLogger("transformers").setLevel(logging.WARNING)
