"""
utils/logging.py
Logging utilities with structlog.

Phase 29: Protocol-based design.

Provides structured logging setup for MCP servers.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
    server_name: str = "mcp",
) -> logging.Logger:
    """Configure structured logging for MCP servers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format type - "json" for JSON logs, "console" for pretty print
        server_name: Server identifier for log context

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Use stdlib logger factory with a standard logger that has 'disabled' attribute
    # This avoids AttributeError with PrintLogger in test environments
    stdlib_logger = logging.getLogger("structlog")
    stdlib_logger.setLevel(log_level)

    if log_format == "json":
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.ProxyLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=False,
        )
    else:
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.ProxyLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=False,
        )

    log = structlog.get_logger(server_name)
    log.info("logging.initialized", level=log_level, format=log_format)
    return log


def get_logger(name: str = "mcp") -> structlog.BoundLogger:
    """Get a logger instance.

    Args:
        name: Logger name (will be prefixed with "mcp.")

    Returns:
        BoundLogger instance
    """
    return structlog.get_logger(f"mcp.{name}")


__all__ = ["setup_logging", "get_logger"]
