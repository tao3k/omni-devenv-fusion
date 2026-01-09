"""
agent/skills/core/task.py - @script_task Decorator (Phase 35.2)

Provides the @script_task decorator for atomic script implementations.

Features:
- Makes scripts importable as modules (for tools.py routing)
- Makes scripts directly executable via CLI (python script.py)
- Optional Prefect-style task metadata
- Logging, timing, and error handling

Usage:
    from agent.skills.core.task import script_task

    @script_task(name="cleanup_logs", timeout=300)
    def cleanup_logs(days: int = 7):
        '''Clean up logs older than N days.'''
        print(f"Cleaning logs older than {days} days...")
        return True

    # In tools.py:
    from .scripts import cleanup_logs
    @skill_command
    def cleanup_logs_cmd(days: int = 7):
        return cleanup_logs(days)
"""

import functools
import time
import logging
from typing import Any, Callable, Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class TaskMetadata:
    """Metadata for a script task (Prefect-style)."""

    def __init__(
        self,
        name: Optional[str] = None,
        description: str = "",
        tags: list[str] = None,
        timeout: Optional[int] = None,
        retry_on_failure: bool = False,
        retry_count: int = 3,
    ):
        self.name = name
        self.description = description
        self.tags = tags or []
        self.timeout = timeout  # seconds
        self.retry_on_failure = retry_on_failure
        self.retry_count = retry_count
        self.created_at = time.time()


def script_task(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: str = "",
    tags: list[str] = None,
    timeout: Optional[int] = None,
    retry_on_failure: bool = False,
    retry_count: int = 3,
) -> Callable:
    """
    Decorator for atomic script tasks.

    Makes a function:
    1. Importable as a module (for tools.py routing)
    2. Directly executable via CLI (python script.py)
    3. Enhanced with logging, timing, and error handling

    Args:
        func: The function to decorate
        name: Task name (defaults to function name)
        description: Task description
        tags: Tags for categorization
        timeout: Maximum execution time in seconds
        retry_on_failure: Whether to retry on failure
        retry_count: Number of retry attempts

    Example:
        from agent.skills.core.task import script_task

        @script_task(name="cleanup", description="Clean up old files")
        def cleanup(pattern: str, days: int = 7):
            print(f"Cleaning {pattern} older than {days} days")
            return True

        # Run from tools.py:
        from .scripts import cleanup
        cleanup(pattern="*.log", days=7)
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs) -> Any:
            task_name = name or f.__name__
            start_time = time.time()

            logger.info(f"Starting task: {task_name}")

            try:
                if timeout:
                    import signal

                    def timeout_handler(signum, frame):
                        raise TimeoutError(f"Task {task_name} timed out after {timeout}s")

                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(timeout)

                result = f(*args, **kwargs)

                if signal.alarm(0):  # Cancel alarm if it was set
                    pass

                elapsed = time.time() - start_time
                logger.info(f"Task {task_name} completed in {elapsed:.2f}s")
                return result

            except TimeoutError as e:
                logger.error(f"Task {task_name} timed out: {e}")
                if retry_on_failure and retry_count > 0:
                    logger.info(f"Retrying {task_name} ({retry_count} attempts left)")
                    return wrapper(*args, **kwargs)
                raise

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"Task {task_name} failed after {elapsed:.2f}s: {e}")
                if retry_on_failure and retry_count > 0:
                    logger.info(f"Retrying {task_name} ({retry_count} attempts left)")
                    return wrapper(*args, **kwargs)
                raise

        # Mark the function as a task
        wrapper._is_script_task = True
        wrapper._task_metadata = TaskMetadata(
            name=name or f.__name__,
            description=description or f.__doc__ or "",
            tags=tags or [],
            timeout=timeout,
            retry_on_failure=retry_on_failure,
            retry_count=retry_count,
        )

        # Enable CLI execution
        def _cli_entrypoint():
            import sys
            import argparse
            from typing import get_type_hints

            parser = argparse.ArgumentParser(description=description or f.__doc__ or "")
            parser.add_argument("args", nargs="*", help="Positional arguments for the task")

            # Add type-hinted arguments
            try:
                hints = get_type_hints(f)
            except Exception:
                hints = {}

            for param_name, param_type in hints.items():
                if param_name in ("self", "cls"):
                    continue
                parser.add_argument(
                    f"--{param_name.replace('_', '-')}",
                    type=param_type,
                    help=f"Argument {param_name} ({param_type.__name__})",
                )

            parsed = parser.parse_args()
            args_dict = vars(parsed)
            result = f(**args_dict)
            if result is not None:
                print(result)

        wrapper._cli = _cli_entrypoint

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def is_script_task(func: Callable) -> bool:
    """Check if a function is decorated with @script_task."""
    return getattr(func, "_is_script_task", False)


def get_task_metadata(func: Callable) -> Optional[TaskMetadata]:
    """Get task metadata from a decorated function."""
    return getattr(func, "_task_metadata", None)


def run_script_as_cli():
    """
    Entry point for running a script directly.

    Usage in script file:
        if __name__ == "__main__":
            from agent.skills.core.task import run_script_as_cli
            run_script_as_cli()
    """
    import sys
    from pathlib import Path

    # Get the calling module's file
    module_file = Path(sys.argv[0]).resolve()

    # Import the module
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"script_{module_file.stem}", str(module_file))
    if spec is None or spec.loader is None:
        print(f"Error: Cannot load module from {module_file}")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    sys.modules[f"script_{module_file.stem}"] = module
    spec.loader.exec_module(module)

    # Find and run the task function
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if is_script_task(attr) and callable(attr):
            attr._cli()
            return

    print(f"No @script_task decorated function found in {module_file}")
    sys.exit(1)


# ==============================================================================
# Example Usage
# ==============================================================================

if __name__ == "__main__":
    # Example: How a user would write their scripts/cleanup.py

    """
    # scripts/cleanup.py
    from agent.skills.core.task import script_task

    @script_task(
        name="cleanup_logs",
        description="Clean up old log files",
        tags=["maintenance", "cleanup"],
        timeout=300,
    )
    def cleanup_logs(pattern: str = "*.log", days: int = 7):
        '''Clean up log files older than N days.'''
        import os
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0

        for f in glob.glob(pattern, recursive=True):
            mtime = datetime.fromtimestamp(Path(f).stat().st_mtime)
            if mtime < cutoff:
                os.remove(f)
                cleaned += 1

        return f"Cleaned {cleaned} files"

    if __name__ == "__main__":
        run_script_as_cli()
    """
    print(__doc__)
