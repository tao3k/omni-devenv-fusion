"""
agent/core/registry/jit.py
Phase 29: JIT Skill Acquisition

Just-in-Time skill installation and discovery.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from common.config.settings import get_setting

# Lazy logger - defer structlog.get_logger() to avoid import-time overhead
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


if TYPE_CHECKING:
    import structlog


def jit_install_skill(
    skill_id: str,
    auto_load: bool = True,
    registry: "SkillRegistry | None" = None,
) -> dict[str, Any]:
    """
    Just-in-Time Skill Installation.

    Automatically install a skill from the known skills index.

    Args:
        skill_id: Skill ID from known_skills.json
        auto_load: Whether to load after installation
        registry: SkillRegistry instance

    Returns:
        Dict with success status and details
    """
    from agent.core.registry.core import SkillRegistry
    from agent.core.registry.installer import RemoteInstaller
    from agent.core.skill_discovery import SkillDiscovery

    if registry is None:
        registry = SkillRegistry()

    discovery = SkillDiscovery()

    # Find skill in index
    skill = discovery.find_by_id(skill_id)
    if not skill:
        results = discovery.search_local(skill_id, limit=1)
        if results:
            skill = results[0]
        else:
            return {
                "success": False,
                "error": f"Skill '{skill_id}' not found in known skills index",
            }

    skill_name = skill["id"]
    repo_url = skill["url"]
    version = skill.get("version", "main")

    # Check if already installed
    target_dir = registry.skills_dir / skill_name
    if target_dir.exists():
        return {
            "success": False,
            "error": f"Skill '{skill_name}' is already installed",
            "path": str(target_dir),
        }

    # Install the skill
    installer = RemoteInstaller(registry)
    success, msg = installer.install(target_dir, repo_url, version)

    if not success:
        return {"success": False, "error": msg}

    # Security scan
    security_result = security_scan_skill(target_dir, repo_url)
    if not security_result["passed"]:
        return {
            "success": False,
            "error": f"Security scan failed",
            "path": str(target_dir),
            "security_report": security_result.get("report", {}),
        }

    # Optionally load
    loaded = False
    load_msg = ""
    if auto_load:
        try:
            from agent.mcp_server import mcp
            from agent.core.registry.loader import SkillLoader

            loader = SkillLoader(registry)
            success, load_msg = loader.load_skill(skill_name, mcp)
            loaded = success
        except Exception as e:
            load_msg = str(e)

    return {
        "success": True,
        "skill_id": skill_id,
        "skill_name": skill_name,
        "url": repo_url,
        "version": version,
        "installed_path": str(target_dir),
        "loaded": loaded,
        "load_message": load_msg if loaded else f"Load skipped: {load_msg}",
    }


def security_scan_skill(target_dir: Path, repo_url: str) -> dict[str, Any]:
    """
    Security scan for JIT installed skill.
    """
    if not get_setting("security.enabled", True):
        return {"passed": True, "error": None, "report": {}}

    try:
        from agent.core.security.immune_system import ImmuneSystem, Decision

        immune = ImmuneSystem()
        assessment = immune.assess(target_dir)

        report = assessment.to_dict()

        if assessment.decision == Decision.BLOCK:
            return {
                "passed": False,
                "error": f"Security concerns detected",
                "report": report,
            }
        elif assessment.decision == Decision.WARN:
            return {"passed": True, "error": None, "report": report}
        else:
            return {"passed": True, "error": None, "report": report}

    except Exception as e:
        return {"passed": True, "error": str(e), "report": {"error": str(e)}}


def discover_skills(query: str = "", limit: int = 5) -> dict[str, Any]:
    """
    Search the known skills index for matching skills.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        Dict with query results
    """
    from agent.core.skill_discovery import SkillDiscovery

    discovery = SkillDiscovery()
    results = discovery.search_local(query, limit)

    return {
        "query": query,
        "count": len(results),
        "skills": results,
        "ready_to_install": [s["id"] for s in results],
    }


def suggest_skills_for_task(task: str) -> dict[str, Any]:
    """
    Analyze a task and suggest relevant skills.

    Args:
        task: Task description

    Returns:
        Dict with task analysis and skill suggestions
    """
    from agent.core.skill_discovery import SkillDiscovery

    discovery = SkillDiscovery()
    return discovery.suggest_for_query(task)


def list_installed_skills(
    registry: "SkillRegistry | None" = None,
) -> list[dict[str, Any]]:
    """
    List all installed skills with their versions.

    Args:
        registry: SkillRegistry instance

    Returns:
        List of skill info dicts
    """
    from agent.core.registry.core import SkillRegistry
    from agent.core.registry.resolver import VersionResolver

    if registry is None:
        registry = SkillRegistry()

    skills = []
    for skill_name in registry.list_available_skills():
        info = registry.get_skill_info(skill_name)
        skills.append(info)

    return skills
