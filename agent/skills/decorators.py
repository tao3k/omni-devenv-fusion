"""
agent/skills/decorators.py
Phase 25.1: Omni Skill Macros.
Provides metadata tagging and dependency injection for skill commands.
"""

import functools
import inspect
from typing import List, Optional, Any, Callable

# Import from common (not mcp_core - these are general utilities)
from common.config_paths import get_project_root
from common.settings import get_setting


def skill_command(
    name: Optional[str] = None,
    category: str = "general",
    description: Optional[str] = None,
    # Dependency Injection Flags
    inject_root: bool = False,
    inject_settings: Optional[List[str]] = None,
):
    """
    [Macro] Mark a function as an exposed skill command with optional DI.

    Args:
        name: Override command name (default: function name)
        category: Grouping for help display (e.g. "git", "file")
        description: Override docstring description
        inject_root: If True, passes 'project_root' (Path) to the function
        inject_settings: List of setting keys to inject (e.g. ["git.path"])
                         Keys are converted to snake_case kwargs (e.g. git_path)

    Usage:
        @skill_command(category="git", description="Check git status")
        def git_status(): ...

        @skill_command(category="git", inject_root=True)
        def status(project_root: Path): ...

        @skill_command(category="git", inject_settings=["git.user", "git.email"])
        def setup_config(git_user: str = None, git_email: str = None): ...
    """

    def decorator(func: Callable) -> Callable:
        # 1. Attach Metadata (used by SkillManager)
        func._is_skill_command = True
        func._skill_config = {
            "name": name or func.__name__,
            "category": category,
            "description": description or _extract_description(func),
        }

        # 2. Dependency Injection Wrapper
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Inject Project Root
            if inject_root and "project_root" not in kwargs:
                kwargs["project_root"] = get_project_root()

            # Inject Settings
            if inject_settings:
                for key in inject_settings:
                    # "git.token" -> "git_token"
                    arg_name = key.replace(".", "_")
                    if arg_name not in kwargs:
                        val = get_setting(key)
                        kwargs[arg_name] = val

            # Execute
            return func(*args, **kwargs)

        # 3. Async Wrapper (separate to preserve async behavior)
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Inject Project Root
            if inject_root and "project_root" not in kwargs:
                kwargs["project_root"] = get_project_root()

            # Inject Settings
            if inject_settings:
                for key in inject_settings:
                    arg_name = key.replace(".", "_")
                    if arg_name not in kwargs:
                        val = get_setting(key)
                        kwargs[arg_name] = val

            # Execute async function
            return await func(*args, **kwargs)

        # Choose wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


def _extract_description(func: Callable) -> str:
    """Extract first line of docstring as description."""
    if func.__doc__:
        lines = [line.strip() for line in func.__doc__.split("\n") if line.strip()]
        return lines[0] if lines else ""
    return ""
