"""
utils.py - Shim Decorator for Heavy Skills

This is a local dummy decorator that allows crawl4ai scripts to:
1. Run in their isolated uv environment without requiring the 'agent' package
2. Be discovered by Rust Scanner via static analysis (decorators preserve signatures)
3. Keep the same code style as regular skills

Usage:
    from .utils import skill_command

    @skill_command(
        name="crawl_url",
        description="Crawl a web page...",
    )
    async def crawl(url: str):
        ...
"""

import functools
from collections.abc import Callable


def skill_command(**kwargs):
    """
    Dummy decorator for Heavy Skills.

    This decorator:
    1. Preserves the original function signature and docstring
    2. Marks the function for Rust Scanner detection
    3. Stores metadata for potential runtime use (uses _skill_config for compatibility)

    Note: This runs in crawl4ai's isolated environment where 'agent' is not installed.
    The real decorator is only used when running in the main agent process.
    """

    def decorator(func: Callable) -> Callable:
        # Preserve function metadata
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        # Mark for scanner detection
        wrapper._is_skill_command = True
        # Use _skill_config for compatibility with script_loader.py
        wrapper._skill_config = kwargs

        return wrapper

    return decorator
