"""
src/agent/core/bootstrap.py
System boot sequence and background task initialization.
"""
import sys
import asyncio
import threading
import structlog
from mcp.server.fastmcp import FastMCP
from agent.core.skill_registry import get_skill_registry
from common.mcp_core import log_decision

logger = structlog.get_logger(__name__)

# Core skills that must be loaded for the agent to be functional
CORE_SKILLS = ["filesystem", "git", "terminal", "testing_protocol"]


def boot_core_skills(mcp: FastMCP):
    """
    [Kernel Boot] Auto-load essential skills to ensure Agent is capable immediately.
    Fixes the 'Lobotomized Agent' issue by ensuring tools like 'smart_commit' are ready.
    """
    registry = get_skill_registry()

    print("🚀 Booting Omni-DevEnv Kernel...", file=sys.stderr)

    for skill in CORE_SKILLS:
        try:
            # Check if skill exists before trying to load
            if registry.get_skill_manifest(skill):
                success, msg = registry.load_skill(skill, mcp)
                if success:
                    print(f"  ✅ Auto-loaded: {skill}", file=sys.stderr)
                    log_decision(f"boot.skill_loaded", {"skill": skill}, logger)
                else:
                    print(f"  ⚠️  Skipped: {skill} -> {msg}", file=sys.stderr)
                    log_decision(f"boot.skill_skipped", {"skill": skill, "reason": msg}, logger)
            else:
                print(f"  ⚠️  Not found: {skill}", file=sys.stderr)
        except Exception as e:
            # Don't crash main process if a skill is malformed
            logger.warning(f"Skill boot error ({skill}): {e}")


def start_background_tasks():
    """
    [Background] Initialize Knowledge Base ingestion in a separate thread.
    Does not block server startup.
    """
    def _run_ingest():
        try:
            from agent.capabilities.knowledge_ingestor import ingest_all_knowledge
            from agent.capabilities.librarian import bootstrap_knowledge

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _async_task():
                try:
                    await ingest_all_knowledge()
                    await bootstrap_knowledge()
                    logger.info("Knowledge base bootstrap completed")
                except Exception as e:
                    logger.error(f"Knowledge base bootstrap failed: {e}")

            loop.run_until_complete(_async_task())
            loop.close()
        except Exception as e:
            logger.error(f"Background thread error: {e}")

    thread = threading.Thread(target=_run_ingest, daemon=True)
    thread.start()
    logger.info("Background tasks started")


__all__ = ["boot_core_skills", "start_background_tasks", "CORE_SKILLS"]
