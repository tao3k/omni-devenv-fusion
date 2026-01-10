"""
log_config.py - Global logging configuration

Phase 35.2: UNIX Philosophy - logs go to stderr, results go to stdout.

This module provides global logging configuration that ensures:
- All system logs go to stderr (visible to user, invisible to pipes)
- stdout stays clean for skill results only

Usage:
    from common.log_config import configure_logging
    configure_logging(level="INFO")
"""

from __future__ import annotations

import sys
import logging
from typing import Optional

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure global logging to send all logs to stderr.

    This ensures stdout stays clean for skill results only.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 1. Configure standard logging (captures all third-party library logs)
    root_logger = logging.getLogger()
    root_logger.handlers = []  # Clear default handlers

    # Key: StreamHandler uses sys.stderr
    stderr_handler = logging.StreamHandler(sys.stderr)

    # Simple format, specific rendering handled by structlog or rich
    formatter = logging.Formatter("%(message)s")
    stderr_handler.setFormatter(formatter)

    root_logger.addHandler(stderr_handler)
    root_logger.setLevel(log_level)

    # 2. Configure Structlog (for internal structured logging)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # ConsoleRenderer renders colors, but final print goes through logging handler (stderr)
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> structlog.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name

    Returns:
        BoundLogger instance
    """
    return structlog.get_logger(name)


# Type alias for log handlers
LogHandler = Optional[callable]


__all__ = ["configure_logging", "get_logger", "LogHandler"]
