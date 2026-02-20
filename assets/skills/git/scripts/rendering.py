"""
git/scripts/rendering.py - Cascading Template Rendering

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

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import jinja2

from omni.foundation.config.settings import get_setting

# ODF Core Imports: SSOT path resolution
from omni.foundation.runtime.gitops import get_git_toplevel, get_project_root


def _get_search_paths() -> list:
    """
    Get template search paths for cascading loader.

    Returns:
        List of paths [skill_default, user_override, ...]
    """
    # Resolve workspace root from this module location first so temporary test
    # git repos (cwd/project_root) do not break skill template discovery.
    module_dir = Path(__file__).resolve().parent
    try:
        workspace_root = get_git_toplevel(module_dir)
    except RuntimeError:
        workspace_root = get_project_root()

    # Path 1: Skill-local default templates (Primary)
    skill_templates_dir = module_dir.parent / "templates"

    # Path 2: User override templates (Fallback - from assets/templates/git/)
    templates_config = get_setting("assets.templates_dir")
    user_templates_root = workspace_root / templates_config
    user_git_templates = user_templates_root / "git"

    # Return valid paths only (skill first, then user)
    return [p for p in [skill_templates_dir, user_git_templates] if p.exists()]


@lru_cache(maxsize=1)
def _get_jinja_env() -> jinja2.Environment:
    """
    Get cached Jinja2 environment with cascading loader.

    Search Path (Priority: High -> Low):
        1. Skill Defaults: assets/skills/git/templates/
        2. User Overrides: assets/templates/git/

    Jinja2 loads first matching template from search paths.
    """
    search_paths = _get_search_paths()

    # Fallback: project_root if nothing found
    if not search_paths:
        search_paths = [get_project_root()]

    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(search_paths),
        autoescape=False,  # Markdown doesn't need HTML escape
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_commit_message(
    subject: str,
    body: str = "",
    status: str = "committed",
    commit_hash: str = "",
    file_count: int = 0,
    verified_by: str = "omni Git Skill (cog)",
    security_status: str = "No sensitive files detected",
    security_issues: list[str] | None = None,
    error: str = "",
    workflow_id: str = "",
    commit_type: str = "feat",
    commit_scope: str = "general",
    submodule_section: str = "",
) -> str:
    """
    Render commit message using cascading Jinja2 template.

    Template resolution:
        - First checks: assets/skills/git/templates/commit_message.j2 (skill default)
        - Falls back to: assets/templates/git/commit_message.j2 (user override)

    Args:
        subject: Commit subject line
        body: Extended commit description
        status: Commit status (committed, security_violation, error, failed)
        commit_hash: Commit hash (for committed status)
        file_count: Number of files changed
        verified_by: Who verified the commit
        security_status: Security scan result message
        security_issues: List of security issues (for security_violation status)
        error: Error message (for error/failed status)
        workflow_id: Workflow ID for tracking (optional)
        commit_type: Conventional commit type (feat, fix, refactor, etc.)
        commit_scope: Commit scope (e.g., git-workflow, core, etc.)
        submodule_section: Additional section showing submodule commits (optional)

    Returns:
        Formatted commit message with verification badge
    """
    env = _get_jinja_env()
    template = env.get_template("commit_message.j2")

    return template.render(
        subject=subject,
        body=body,
        status=status,
        commit_hash=commit_hash,
        file_count=file_count,
        verified_by=verified_by,
        security_status=security_status,
        security_issues=security_issues or [],
        error=error,
        workflow_id=workflow_id,
        commit_type=commit_type,
        commit_scope=commit_scope,
        submodule_section=submodule_section,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def render_workflow_result(
    intent: str,
    success: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> str:
    """
    Render workflow execution result.

    Template resolution:
        - First checks: assets/skills/git/templates/workflow_result.j2 (skill default)
        - Falls back to: assets/templates/git/workflow_result.j2 (user override)

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
    suggestion: str | None = None,
) -> str:
    """
    Render error message for LLM parsing.

    Template resolution:
        - First checks: assets/skills/git/templates/error_message.j2 (skill default)
        - Falls back to: assets/templates/git/error_message.j2 (user override)

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


def list_templates() -> dict[str, dict[str, str]]:
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


def get_template_info(template_name: str) -> dict[str, str] | None:
    """
    Get information about a specific template.

    Args:
        template_name: Template filename (e.g., "commit_message.j2")

    Returns:
        Dict with source, path, or None if not found
    """
    templates = list_templates()
    return templates.get(template_name)


def get_template_source(template_name: str) -> str | None:
    """Get the source code of a template (for debugging)."""
    try:
        env = _get_jinja_env()
        template = env.get_template(template_name)
        return template.source
    except jinja2.TemplateNotFound:
        return None


def render_template(template_name: str, **context) -> str:
    """
    Render any Jinja2 template with cascading support.

    Template resolution:
        - First checks: assets/templates/git/ (user override)
        - Falls back to: assets/skills/git/templates/ (skill default)

    Args:
        template_name: Template filename (e.g., "review_card.j2")
        **context: Variables to pass to template

    Returns:
        Rendered template string
    """
    env = _get_jinja_env()
    template = env.get_template(template_name)
    return template.render(**context)
