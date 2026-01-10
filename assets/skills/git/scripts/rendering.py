"""
git/scripts/rendering.py - Cascading Template Rendering (Phase 35.2)

Implements "User Overrides > Skill Defaults" cascading loader pattern.

Architecture:
    workflow.py  -> Logic (preparation, validation)
    rendering.py -> Presentation (Jinja2 templates with cascading loader)

Template Loading Strategy:
    1. User Overrides: assets/templates/git/ (highest priority)
    2. Skill Defaults: assets/skills/git/templates/ (fallback)
    3. Project Root: Fallback to prevent loader errors

SSOT: All paths resolved via common.skills_path and common.config.settings

Performance:
    - Uses lru_cache for template environment (loaded once)
    - Lazy initialization of search paths
    - Auto-escaping for HTML/XML safety
    - Structured output for LLM parsing

Usage:
    from .rendering import render_commit_message

    result = render_commit_message(
        subject="feat(git): add commit workflow",
        body="- Improved commit message formatting\n- Added verification badge",
        verified=True,
        checks=["lefthook passed", "scope validated"]
    )
"""

import jinja2
from functools import lru_cache
from datetime import datetime
from typing import Optional, List, Dict, Any

# ODF Core Imports: SSOT path resolution
from common.skills_path import SKILLS_DIR
from common.config.settings import get_setting
from common.gitops import get_project_root


def _get_search_paths() -> list:
    """
    Get template search paths for cascading loader.

    Returns:
        List of paths [user_override, skill_default, ...]
    """
    project_root = get_project_root()

    # Path 1: User override templates (Priority)
    templates_config = get_setting("assets.templates_dir", "assets/templates")
    user_templates_root = project_root / templates_config
    user_git_templates = user_templates_root / "git"

    # Path 2: Skill-local default templates (Fallback)
    skill_templates_dir = SKILLS_DIR("git", path="templates")

    # Return valid paths only
    return [p for p in [user_git_templates, skill_templates_dir] if p.exists()]


@lru_cache(maxsize=1)
def _get_jinja_env() -> jinja2.Environment:
    """
    Get cached Jinja2 environment with cascading loader.

    Search Path (Priority: High -> Low):
        1. User Overrides: assets/templates/git/
        2. Skill Defaults: assets/skills/git/templates/

    Jinja2 loads first matching template from search paths.
    """
    search_paths = _get_search_paths()

    # Fallback: project_root if nothing found
    if not search_paths:
        search_paths = [get_project_root()]

    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(search_paths),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_commit_message(
    subject: str,
    body: str = "",
    verified: bool = True,
    checks: Optional[List[str]] = None,
    status: str = "ready",
    security_passed: bool = True,
    security_warning: str = "",
) -> str:
    """
    Render commit message using cascading Jinja2 template.

    Template resolution:
        - First checks: assets/templates/git/commit_message.j2 (user override)
        - Falls back to: assets/skills/git/templates/commit_message.j2 (skill default)

    Args:
        subject: Commit subject line
        body: Extended commit description
        verified: Whether the commit is verified
        checks: List of verification checks passed
        status: Commit status (ready, draft, etc.)
        security_passed: Whether security guard check passed
        security_warning: Security warning message if any sensitive files detected

    Returns:
        Formatted commit message with verification badge
    """
    env = _get_jinja_env()
    template = env.get_template("commit_message.j2")

    # Default checks if not provided
    if checks is None:
        checks = ["Pre-commit hooks passed"]

    return template.render(
        subject=subject,
        body=body,
        verified=verified,
        checks=checks,
        status=status,
        timestamp=datetime.now().isoformat(),
        security_passed=security_passed,
        security_warning=security_warning,
    )


def render_workflow_result(
    intent: str,
    success: bool,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Render workflow execution result.

    Template resolution:
        - First checks: assets/templates/git/workflow_result.j2 (user override)
        - Falls back to: assets/skills/git/templates/workflow_result.j2 (skill default)

    Args:
        intent: Workflow intent (hotfix, commit, branch, etc.)
        success: Whether the workflow succeeded
        message: Result message
        details: Additional details dict

    Returns:
        Formatted workflow result
    """
    env = _get_jinja_env()
    template = env.get_template("workflow_result.j2")

    return template.render(
        intent=intent,
        success=success,
        message=message,
        details=details or {},
        timestamp=datetime.now().isoformat(),
    )


def render_error(
    error_type: str,
    message: str,
    suggestion: Optional[str] = None,
) -> str:
    """
    Render error message for LLM parsing.

    Template resolution:
        - First checks: assets/templates/git/error_message.j2 (user override)
        - Falls back to: assets/skills/git/templates/error_message.j2 (skill default)

    Args:
        error_type: Type of error (validation, execution, etc.)
        message: Error message
        suggestion: Suggested fix

    Returns:
        Formatted error with suggestions
    """
    env = _get_jinja_env()
    template = env.get_template("error_message.j2")

    return template.render(
        error_type=error_type,
        message=message,
        suggestion=suggestion,
        timestamp=datetime.now().isoformat(),
    )


# =============================================================================
# Template Discovery & Info (for debugging/CLI)
# =============================================================================


def list_templates() -> Dict[str, Dict[str, str]]:
    """
    List all available git templates with their source locations.

    Returns:
        Dict mapping template_name -> {"source": "user|skill", "path": absolute_path}
    """
    env = _get_jinja_env()
    search_paths = _get_search_paths()

    templates_info = {}

    for template_name in env.list_templates():
        if not template_name.endswith(".j2"):
            continue

        # Find which path this template comes from
        for search_path in search_paths:
            potential_path = search_path / template_name
            if potential_path.exists():
                is_user = "templates/git" in str(potential_path)
                templates_info[template_name] = {
                    "source": "user" if is_user else "skill",
                    "path": str(potential_path),
                }
                break

    return templates_info


def get_template_info(template_name: str) -> Optional[Dict[str, str]]:
    """
    Get information about a specific template.

    Args:
        template_name: Template filename (e.g., "commit_message.j2")

    Returns:
        Dict with source, path, or None if not found
    """
    templates = list_templates()
    return templates.get(template_name)


def get_template_source(template_name: str) -> Optional[str]:
    """Get the source code of a template (for debugging)."""
    try:
        env = _get_jinja_env()
        template = env.get_template(template_name)
        return template.source
    except jinja2.TemplateNotFound:
        return None
