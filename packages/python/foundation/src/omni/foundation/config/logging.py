"""
logging.py - Global logging configuration

Trinity Architecture - Foundation Layer

Beautiful structured logging with ANSI colors:
- Color-coded log levels (DEBUG=gray, INFO=green, WARNING=yellow, ERROR=red)
- Timestamps with consistent formatting
- Logger name/module visible
- Structured key=value pairs beautifully rendered

Example output:
    2024-01-21 10:30:45 [INFO    ] omni.core.kernel: Kernel initializing...
    2024-01-21 10:30:45 [INFO    ] omni.core.kernel: 🟢 Kernel ready - 5 skills active
    2024-01-21 10:30:46 [ERROR   ] omni.agent.server: 💥 Server crashed error=Connection refused

Usage:
    from omni.foundation.config.logging import configure_logging, get_logger
    configure_logging(level="INFO")
    logger = get_logger("my.module")
    logger.info("Starting...", event="startup")
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog

# =============================================================================
# ANSI Color Codes
# =============================================================================


class Colors:
    """ANSI color codes for terminal output."""

    # Reset
    RESET = "\033[0m"

    # Styles
    DIM = "\033[2m"
    BOLD = "\033[1m"
    REVERSE = "\033[7m"

    # Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors (for timestamp/debug)
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# Color mapping for log levels
LOG_COLORS = {
    "DEBUG": f"{Colors.BRIGHT_BLACK}{Colors.DIM}",
    "INFO": Colors.GREEN,
    "WARNING": Colors.YELLOW,
    "ERROR": f"{Colors.RED}{Colors.BOLD}",
    "CRITICAL": f"{Colors.RED}{Colors.BOLD}{Colors.REVERSE}",
}

# Reset code
RESET = Colors.RESET


# =============================================================================
# Beautiful Formatter
# =============================================================================


def format_log(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> str:
    """Format a log entry with beautiful colors.

    Args:
        _logger: The logger instance (unused)
        _method_name: The log method name (info, error, etc.)
        event_dict: The event dictionary containing event and other data

    Returns:
        Formatted log string with ANSI colors
    """
    # Get colors setting from event_dict or use global forced value
    colors = event_dict.pop("_colors", None)
    if colors is None:
        colors = _force_colors

    # Extract message
    msg = event_dict.get("event", "")

    if not colors:
        # Plain text output
        return _format_plain(_method_name, msg, event_dict)

    # Colored output
    return _format_rich(_method_name, msg, event_dict)


def _format_rich(level: str, msg: str, data: dict[str, Any]) -> str:
    """Format with ANSI colors."""
    # Get color for level
    level_upper = level.upper()
    color = LOG_COLORS.get(level_upper, "")

    # Build timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build the line
    parts = [
        f"{Colors.BRIGHT_BLACK}{timestamp}{RESET}",
        f"{color}[{level_upper:<8}]{RESET}",
    ]

    # Add logger name if present
    logger_name = data.get("logger", "") or data.get("logger_name", "")
    if logger_name:
        parts.append(f"{Colors.CYAN}{logger_name}:{RESET}")

    # Add message
    parts.append(msg)

    # Add key=value pairs (exclude common keys)
    extra = {
        k: v for k, v in data.items() if k not in ("logger", "logger_name", "event", "_colors")
    }
    if extra:
        for key, value in extra.items():
            parts.append(f"{Colors.MAGENTA}{key}={RESET}{Colors.GREEN}{value}{RESET}")

    return " ".join(parts)


def _format_plain(level: str, msg: str, data: dict[str, Any]) -> str:
    """Format without colors."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level_upper = level.upper()

    parts = [f"{timestamp} [{level_upper:<8}]"]

    logger_name = data.get("logger", "") or data.get("logger_name", "")
    if logger_name:
        parts.append(f"{logger_name}:")
    parts.append(msg)

    extra = {
        k: v for k, v in data.items() if k not in ("logger", "logger_name", "event", "_colors")
    }
    if extra:
        parts.append(" " + " ".join(f"{k}={v}" for k, v in extra.items()))

    return " ".join(parts)


# =============================================================================
# Subprocess Log Filter
# =============================================================================


class SubprocessLogFilter(logging.Filter):
    """Filter out non-structured subprocess logs (e.g., Popen debug output from GitPython)."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "Popen(['git'" in msg or "subprocess.Popen" in msg:
            return False
        return True


# =============================================================================
# Safe Stream Handler (for concurrent tests)
# =============================================================================


class _SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that safely handles closed file handles in tests.

    Prevents "I/O operation on closed file" errors when pytest workers
    shut down but background threads still try to log.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.stream and hasattr(self.stream, "closed") and self.stream.closed:
                return
            super().emit(record)
        except Exception:
            pass  # Silently ignore logging errors during shutdown


def _configure_safe_logging() -> None:
    """Configure logging handlers to safely handle closed file handles."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            handler.__class__ = _SafeStreamHandler


def _setup_log_filters(level: int) -> None:
    """Configure log filter levels for third-party libraries."""
    # Always suppress HTTP tracing logs (connect/send/receive details)
    # These are too verbose for human-readable output
    http_tracing = [
        "httpx.dispatch",
        "httpx.client",
        "httpcore.dispatch",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.pool",
    ]

    for logger_name in http_tracing:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    noisy_loggers = [
        ("uvicorn", logging.WARNING),
        ("uvicorn.access", logging.WARNING),
        ("starlette", logging.WARNING),
        ("httpx", logging.WARNING if level > logging.DEBUG else logging.INFO),
        ("httpcore", logging.WARNING if level > logging.DEBUG else logging.INFO),
    ]

    for logger_name, log_lvl in noisy_loggers:
        logging.getLogger(logger_name).setLevel(log_lvl)


# =============================================================================
# Configuration
# =============================================================================

# Track whether logging has been configured
_configured = False
_force_colors = False  # Global flag for color forcing
_verbose_level = logging.INFO  # Track verbose level for Rust integration


def configure_logging(
    level: str = "INFO",
    colors: bool | None = None,
    verbose: bool = False,
    force: bool = False,
) -> None:
    """Configure global logging with beautiful structured output.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        colors: Enable ANSI colors. If None, auto-detect from TTY.
        verbose: Enable verbose mode (DEBUG level)
        force: Force reconfiguration even if already configured
    """
    global _configured, _force_colors, _verbose_level

    if _configured and not force:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    if verbose:
        log_level = logging.DEBUG

    # Track for Rust integration
    _verbose_level = log_level
    os.environ["OMNI_LOG_LEVEL"] = logging.getLevelName(log_level)

    # Auto-detect colors if not specified
    if colors is None:
        colors = sys.stderr.isatty()

    # Store colors in a global for format_log to access
    global _force_colors
    _force_colors = colors

    # 1. Configure standard logging
    root_logger = logging.getLogger()
    root_logger.handlers = []

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.addFilter(SubprocessLogFilter())
    formatter = logging.Formatter("%(message)s")
    stderr_handler.setFormatter(formatter)

    root_logger.addHandler(stderr_handler)
    root_logger.setLevel(log_level)

    # 2. Configure Structlog with beautiful formatter
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        format_log,
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 3. Configure safe logging for concurrent test environments
    _configure_safe_logging()

    _configured = True

    # 4. Suppress noisy third-party loggers
    _setup_log_filters(log_level)


def get_logger(name: str = "omni") -> structlog.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        BoundLogger instance for structured logging
    """
    return structlog.get_logger(name)


def setup_verbose_logging() -> None:
    """Enable verbose debugging logging."""
    configure_logging(level="DEBUG", verbose=True)


def is_verbose() -> bool:
    """Check if verbose/debug logging is enabled.

    Returns:
        True if DEBUG level logging is enabled
    """
    return _verbose_level <= logging.DEBUG


def get_log_level() -> str:
    """Get the current log level as a string.

    Returns:
        Log level name: DEBUG, INFO, WARNING, ERROR
    """
    return logging.getLevelName(_verbose_level)


# =============================================================================
# Convenience Logging Functions with Beautiful Output
# =============================================================================


def log_banner(title: str, subtitle: str = "System Ready") -> None:
    """Log a startup banner."""
    logger = get_logger("omni.startup")
    logger.info(f"🚀 {title}")
    logger.debug(f"   └── {subtitle}")


def log_ready(component: str, details: str = "") -> None:
    """Log a component ready status."""
    logger = get_logger("omni.ready")
    if details:
        logger.info(f"✅ {component}", detail=details)
    else:
        logger.info(f"✅ {component} ready")


def log_error(component: str, error: str) -> None:
    """Log an error."""
    logger = get_logger("omni.error")
    logger.error(f"❌ {component}", error=error)


def log_loading(component: str, status: str = "loading...") -> None:
    """Log a loading status."""
    logger = get_logger("omni.loading")
    logger.info(f"🔄 {component}: {status}")


def log_task_start(task: str) -> None:
    """Log task start."""
    logger = get_logger("omni.task")
    logger.info(f"▶️  Starting: {task}")


def log_task_done(task: str, duration: float | None = None) -> None:
    """Log task completion."""
    logger = get_logger("omni.task")
    if duration is not None:
        logger.info(f"✅ Done: {task}", duration=f"{duration:.2f}s")
    else:
        logger.info(f"✅ Done: {task}")


def log_data(label: str, data: dict[str, Any]) -> None:
    """Log structured data beautifully."""
    logger = get_logger("omni.data")
    logger.info(f"📊 {label}", **data)


# Type alias for log handlers (PEP 695 syntax)
type LogHandler = Callable[..., Any] | None

__all__ = [
    "Colors",
    "LogHandler",
    "configure_logging",
    "format_log",
    "get_logger",
    "get_log_level",
    "is_verbose",
    "log_banner",
    "log_data",
    "log_error",
    "log_loading",
    "log_ready",
    "log_task_done",
    "log_task_start",
    "setup_verbose_logging",
]
