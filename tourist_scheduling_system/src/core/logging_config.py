#!/usr/bin/env python3
# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
"""
Logging configuration for the Tourist Scheduling System.

Provides centralized logging setup with both console and file output.
Log files are stored in the 'logs' directory with rotation.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_log_dir() -> Path:
    """Get the logs directory, creating it if necessary."""
    # Try to find the project root
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            log_dir = current / "logs"
            break
        current = current.parent
    else:
        # Fallback to current working directory
        log_dir = Path.cwd() / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    name: str,
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True,
    log_dir: Path = None,
) -> logging.Logger:
    """
    Set up logging with console and/or file handlers.

    Args:
        name: Logger name (used for log file name)
        level: Logging level
        console: Enable console output
        file: Enable file output
        log_dir: Custom log directory (defaults to project logs/)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # File handler
    if file:
        if log_dir is None:
            log_dir = get_log_dir()

        # Create log file with timestamp
        safe_name = name.replace("/", "_").replace(".", "_")
        log_file = log_dir / f"{safe_name}.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

        # Also log to a combined log file
        combined_log = log_dir / "combined.log"
        combined_handler = RotatingFileHandler(
            combined_log,
            maxBytes=50 * 1024 * 1024,  # 50 MB
            backupCount=3,
            encoding="utf-8",
        )
        combined_handler.setLevel(level)
        combined_handler.setFormatter(detailed_formatter)
        logger.addHandler(combined_handler)

    return logger


def setup_agent_logging(agent_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Convenience function to set up logging for an agent.

    Args:
        agent_name: Name of the agent (e.g., "scheduler", "ui", "guide")
        level: Logging level

    Returns:
        Configured logger instance
    """
    return setup_logging(
        name=f"agent.{agent_name}",
        level=level,
        console=True,
        file=True,
    )


def setup_root_logging(level: int = logging.INFO):
    """
    Configure root logger for the entire application.

    This sets up logging for all modules that use logging.getLogger().
    """
    log_dir = get_log_dir()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Detailed formatter for files
    detailed_formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console formatter (simpler)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Main log file
    main_log = log_dir / "tourist_scheduling.log"
    file_handler = RotatingFileHandler(
        main_log,
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Debug log file (captures everything)
    debug_log = log_dir / "debug.log"
    debug_handler = RotatingFileHandler(
        debug_log,
        maxBytes=100 * 1024 * 1024,  # 100 MB
        backupCount=2,
        encoding="utf-8",
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(debug_handler)

    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    return root_logger
