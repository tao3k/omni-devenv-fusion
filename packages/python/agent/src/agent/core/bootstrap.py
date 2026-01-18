"""
src/agent/core/bootstrap.py
System boot sequence and background task initialization.
 Config-driven skill preloading for pure MCP Server.
"""

import asyncio
import threading
import structlog
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mcp.server import Server

logger = structlog.get_logger(__name__)


def boot_core_skills(mcp: Optional["Server"] = None):
    """
    [Kernel Boot] Auto-load skills from settings.yaml.
    Fixes the 'Lobotomized Agent' issue by ensuring tools are ready.

    Note: With pure MCP Server, tools are listed dynamically via handle_list_tools.
    This function pre-loads skills into SkillManager for faster first-run.

    Loading mode is controlled by settings.yaml:
    - skills.preload: Skills loaded at startup
    - skills.on_demand: Skills available but not loaded until requested
    """
    # Lazy imports to avoid import-time overhead
    from agent.core.skill_registry import get_skill_registry

    registry = get_skill_registry()

    logger.info("Booting Omni-DevEnv Kernel...")

    # Use config-driven preloading
    preload_skills = registry.get_preload_skills()

    if not preload_skills:
        logger.warning("No preload skills configured in settings.yaml")
        return

    loaded_count = 0
    skipped_count = 0
    for skill in preload_skills:
        try:
            # Check if skill exists before trying to load
            if registry.get_skill_manifest(skill):
                # Load skill (mcp parameter is ignored in pure MCP mode,
                # but kept for API compatibility)
                success, msg = registry.load_skill(skill, mcp)
                if success:
                    loaded_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            # Don't crash main process if a skill is malformed
            logger.warning(f"Skill boot error ({skill}): {e}")

    logger.info(
        "Skills preloaded", loaded=loaded_count, skipped=skipped_count, total=len(preload_skills)
    )


def start_background_tasks() -> threading.Thread | None:
    """
    [Background] Initialize Knowledge Base ingestion in a separate thread.
    Does not block server startup.

    Returns the thread reference so it can be joined on graceful shutdown.
    """
    global _background_thread

    def _run_ingest():
        try:
            from agent.capabilities.knowledge.ingestor import ingest_all_knowledge
            from agent.capabilities.knowledge.librarian import bootstrap_knowledge

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:

                async def _async_task():
                    try:
                        await ingest_all_knowledge()
                        await bootstrap_knowledge()
                        logger.info("Knowledge base bootstrap completed")
                    except Exception as e:
                        logger.error(f"Knowledge base bootstrap failed: {e}")

                loop.run_until_complete(_async_task())
            finally:
                # Ensure loop is properly closed even on exception
                try:
                    loop.close()
                except Exception:
                    pass  # Ignore close errors
        except Exception as e:
            logger.error(f"Background thread error: {e}")

    _background_thread = threading.Thread(target=_run_ingest, daemon=False)
    _background_thread.start()
    logger.info("Background tasks started")

    return _background_thread


# Global reference for shutdown handling
_background_thread: threading.Thread | None = None


def shutdown_background_tasks(timeout: float = 30.0) -> bool:
    """
    Gracefully shutdown background tasks by waiting for thread completion.

    Args:
        timeout: Maximum seconds to wait for thread to finish

    Returns:
        True if thread completed within timeout, False otherwise
    """
    global _background_thread
    if _background_thread and _background_thread.is_alive():
        logger.info("Waiting for background tasks to complete...")
        _background_thread.join(timeout=timeout)
        if _background_thread.is_alive():
            logger.warning("Background tasks did not complete within timeout")
            return False
        logger.info("Background tasks completed")
        return True
    return True


__all__ = ["boot_core_skills", "start_background_tasks", "shutdown_background_tasks"]
