"""
utils.py - Shim Decorator for Heavy Skills

This is a local dummy decorator that allows crawl4ai scripts to:
1. Run in their isolated uv environment without requiring the 'agent' package
2. Be discovered by Rust Scanner via static analysis (decorators preserve signatures)
3. Keep the same code style as regular skills

Usage:
    from .utils import skill_script

    @skill_script(
        name="crawl_url",
        description="Crawl a web page...",
    )
    async def crawl(url: str):
        ...
"""

import functools
from typing import Any, Callable


def skill_script(**kwargs):
    """
    Dummy decorator for Heavy Skills.

    This decorator:
    1. Preserves the original function signature and docstring
    2. Marks the function for Rust Scanner detection
    3. Stores metadata for potential runtime use

    Note: This runs in crawl4ai's isolated environment where 'agent' is not installed.
    The real decorator is only used when running in the main agent process.
    """

    def decorator(func: Callable) -> Callable:
        # Preserve function metadata
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Mark for scanner detection
        wrapper._is_skill_script = True
        wrapper._skill_metadata = kwargs

        return wrapper

    return decorator
