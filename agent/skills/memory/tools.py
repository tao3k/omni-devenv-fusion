"""
agent/skills/memory/tools.py
Memory Skill - The Hippocampus Interface.

Phase 25.1: Macro System with @skill_command decorators.

Role:
  Allows the Agent to semantically store and retrieve knowledge via ChromaDB.
  Replaces rigid file-based logging with fluid vector memory.

Memory Path (from settings.yaml -> prj-spec):
  {git_toplevel}/.cache/{project_name}/.memory/
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)


# =============================================================================
# Path Configuration (Configurable via settings.yaml)
# =============================================================================


def _get_git_toplevel() -> Path:
    """Get git toplevel directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def _get_memory_path() -> Path:
    """
    Get memory root path following prj-spec.
    Configurable via settings.yaml: memory.path
    Falls back to: {git_toplevel}/.cache/{project}/.memory/
    """
    from common.settings import get_setting
    from common.gitops import get_project_root

    custom_path = get_setting("memory.path", "")
    if custom_path:
        return Path(custom_path)

    project = "omni-dev-fusion"
    git_root = get_project_root()
    return git_root / ".cache" / project / "memory"


MEMORY_ROOT = _get_memory_path()
DB_PATH = MEMORY_ROOT / "chroma_db"
DB_PATH.mkdir(parents=True, exist_ok=True)

try:
    client = chromadb.PersistentClient(path=str(DB_PATH))
    episodic_mem = client.get_or_create_collection(name="episodic_memory")
    semantic_mem = client.get_or_create_collection(name="semantic_knowledge")
    CHROMA_AVAILABLE = True
except Exception as e:
    CHROMA_AVAILABLE = False
    client = None
    episodic_mem = None
    semantic_mem = None


@skill_command(
    name="memory_remember_insight",
    category="write",
    description="Store a key insight into ChromaDB.",
)
async def remember_insight(content: str, domain: str = "general") -> str:
    """
    [Long-term Memory] Store a key insight, decision, or learning into ChromaDB.

    Use this when you've learned something reusable:
    - "Use scope 'nix' for flake changes"
    - "The project uses Conventional Commits"
    - "Always run 'just validate' before committing"

    Args:
        content: The insight to store (what you learned)
        domain: Category like "git", "nix", "architecture", "workflow"

    Returns:
        Confirmation message with stored content preview
    """
    if not CHROMA_AVAILABLE:
        return "ChromaDB not available. Cannot store insight."

    timestamp = datetime.now().isoformat()

    try:
        semantic_mem.add(
            documents=[content],
            metadatas=[{"timestamp": timestamp, "domain": domain, "type": "insight"}],
            ids=[f"insight_{timestamp}"],
        )
        return f'Insight stored in Hippocampus:\n[Domain: {domain}]\n"{content[:100]}..."'
    except Exception as e:
        return f"Failed to store insight: {e}"


@skill_command(
    name="memory_log_episode",
    category="write",
    description="Log a significant action taken during the session.",
)
async def log_episode(action: str, result: str, context: str = "") -> str:
    """
    [Short-term Memory] Log a significant action taken during the session.

    Use this for:
    - "Fixed bug in git skill"
    - "Refactored skill registry"
    - "Added new documentation"

    Args:
        action: What you did
        result: What happened (success/failure/observation)
        context: Optional context (file, function, etc.)

    Returns:
        Confirmation of logged episode
    """
    if not CHROMA_AVAILABLE:
        return "ChromaDB not available. Cannot log episode."

    timestamp = datetime.now().isoformat()
    content = f"Action: {action}\nResult: {result}"
    if context:
        content += f"\nContext: {context}"

    try:
        episodic_mem.add(
            documents=[content],
            metadatas=[{"timestamp": timestamp, "type": "episode"}],
            ids=[f"epi_{timestamp}"],
        )
        return f"Episode logged: {action[:50]}..."
    except Exception as e:
        return f"Failed to log episode: {e}"


@skill_command(
    name="memory_recall",
    category="read",
    description="Semantically search memory for relevant past experiences.",
)
async def recall(query: str, n_results: int = 3) -> str:
    """
    [Retrieval] Semantically search memory for relevant past experiences or rules.

    Examples:
    - recall("git commit message format")
    - recall("nixfmt error solution")
    - recall("how to add a new skill")

    Args:
        query: What you're looking for
        n_results: Number of results to return (default: 3)

    Returns:
        Relevant memories found, or "No relevant memories found"
    """
    if not CHROMA_AVAILABLE:
        return "ChromaDB not available. Cannot recall memories."

    if not semantic_mem:
        return "No semantic memory available."

    try:
        results = semantic_mem.query(query_texts=[query], n_results=n_results)

        if not results["documents"][0]:
            return "No relevant memories found."

        memories = []
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            domain = meta.get("domain", "unknown")
            memories.append(f"[{i + 1}] [{domain}] {doc}")

        return f"**Hippocampus Recall**:\n" + "\n---\n".join(memories)
    except Exception as e:
        return f"Recall failed: {e}"


@skill_command(
    name="memory_list_harvested_knowledge",
    category="read",
    description="List all harvested insights stored in memory.",
)
async def list_harvested_knowledge() -> str:
    """
    [Reflection] List all harvested insights stored in memory.

    Returns:
        Formatted list of all stored insights
    """
    if not CHROMA_AVAILABLE or not semantic_mem:
        return "No knowledge available."

    try:
        results = semantic_mem.get(where={"type": "insight"})

        if not results["documents"]:
            return "No harvested knowledge yet."

        by_domain: Dict[str, List[str]] = {}
        for doc, meta in zip(results["documents"], results.get("metadatas", [])):
            domain = meta.get("domain", "general")
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(doc)

        lines = ["Harvested Knowledge", ""]
        for domain, insights in by_domain.items():
            lines.append(f"### {domain.upper()}")
            for i, insight in enumerate(insights):
                lines.append(f"  {i + 1}. {insight[:80]}...")
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list knowledge: {e}"


@skill_command(
    name="memory_harvest_session_insight",
    category="write",
    description="Extract and store key learnings from current session.",
)
async def harvest_session_insight(context_summary: str, files_changed: List[str] = None) -> str:
    """
    [Consolidation] Extract key learnings from current session and store in memory.

    Call this at the end of a significant session to capture:
    - What was accomplished
    - What was learned
    - What should be remembered

    Args:
        context_summary: Summary of what was done and learned
        files_changed: List of files that were modified

    Returns:
        Confirmation of harvested insights
    """
    if not CHROMA_AVAILABLE:
        return "ChromaDB not available. Cannot harvest insights."

    timestamp = datetime.now().isoformat()

    insight = f"Session at {timestamp}:\n{context_summary}"
    if files_changed:
        insight += f"\nFiles changed: {', '.join(files_changed)}"

    try:
        semantic_mem.add(
            documents=[insight],
            metadatas=[{"timestamp": timestamp, "domain": "session", "type": "harvest"}],
            ids=[f"harvest_{timestamp}"],
        )
        return f'Session insight harvested and stored.\n"{context_summary[:100]}..."'
    except Exception as e:
        return f"Harvest failed: {e}"


@skill_command(
    name="memory_get_stats",
    category="view",
    description="Get statistics about stored memories.",
)
async def get_memory_stats() -> str:
    """
    [Diagnostics] Get statistics about stored memories.

    Returns:
        Count of episodic and semantic memories
    """
    if not CHROMA_AVAILABLE:
        return "ChromaDB not available."

    stats = []
    try:
        if semantic_mem:
            semantic_count = semantic_mem.count()
            stats.append(f"Semantic memories (insights): {semantic_count}")

        if episodic_mem:
            episodic_count = episodic_mem.count()
            stats.append(f"Episodic memories (actions): {episodic_count}")

        return "Memory Statistics\n" + "\n".join(stats)
    except Exception as e:
        return f"Stats failed: {e}"


# =============================================================================
# Skill Loader - Load skills into semantic memory
# =============================================================================


def _get_skills_dir() -> Path:
    """Get skills directory path."""
    from common.settings import get_setting
    from common.gitops import get_project_root

    skills_path = get_setting("skills.path", "agent/skills")
    project_root = get_project_root()
    return project_root / skills_path


def _load_manifest(skill_name: str) -> Optional[Dict[str, Any]]:
    """Load a skill's manifest.json."""
    skills_dir = _get_skills_dir()
    manifest_path = skills_dir / skill_name / "manifest.json"

    if not manifest_path.exists():
        return None

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_prompts(skill_name: str) -> Optional[str]:
    """Load a skill's prompts.md if it exists."""
    skills_dir = _get_skills_dir()
    prompts_path = skills_dir / skill_name / "prompts.md"

    if prompts_path.exists():
        return prompts_path.read_text(encoding="utf-8")
    return None


@skill_command(
    name="memory_load_skill",
    category="write",
    description="Load a skill's manifest into semantic memory.",
)
async def load_skill(skill_name: str) -> str:
    """
    [Skill Loader] Load a single skill's manifest into semantic memory.

    Usage:
    - load_skill("git") - Load git skill
    - load_skill("terminal") - Load terminal skill

    This enables LLM to recall skill capabilities via semantic search.

    Returns:
        Confirmation message with skill details
    """
    if not CHROMA_AVAILABLE or not semantic_mem:
        return "ChromaDB not available. Cannot load skill."

    manifest = _load_manifest(skill_name)
    if not manifest:
        return f"Skill '{skill_name}' not found or invalid manifest."

    # Build document from manifest
    routing_kw = manifest.get("routing_keywords", [])
    intents = manifest.get("intents", [])
    deps = manifest.get("dependencies", [])

    document = f"""# {manifest.get("name", skill_name)}

{manifest.get("description", "No description.")}

**Version:** {manifest.get("version", "unknown")}
**Routing Keywords:** {", ".join(routing_kw)}
**Intents:** {", ".join(intents)}
**Dependencies:** {", ".join(deps) if deps else "None"}
"""

    # Append prompts.md content if available
    prompts = _load_prompts(skill_name)
    if prompts:
        document += f"\n---\n\n## System Prompts\n{prompts[:2000]}"

    timestamp = datetime.now().isoformat()
    skill_id = f"skill_{skill_name}"

    try:
        # Upsert skill manifest (replace if exists)
        semantic_mem.delete(ids=[skill_id])
        semantic_mem.add(
            documents=[document],
            metadatas=[
                {
                    "timestamp": timestamp,
                    "type": "skill_manifest",
                    "skill_name": skill_name,
                    "version": manifest.get("version", "unknown"),
                    "routing_keywords": json.dumps(routing_kw),
                    "intents": json.dumps(intents),
                    "domain": "skill",
                }
            ],
            ids=[skill_id],
        )

        return (
            f"✅ Skill '{skill_name}' loaded into semantic memory.\n"
            f"**Routing Keywords:** {', '.join(routing_kw[:5])}..."
        )
    except Exception as e:
        return f"Failed to load skill '{skill_name}': {e}"


@skill_command(
    name="memory_load_activated_skills",
    category="write",
    description="Load all activated skills into semantic memory.",
)
async def load_activated_skills() -> str:
    """
    [Skill Loader] Load all activated skills into semantic memory.

    Reads skills from SkillManager and stores each manifest in ChromaDB.

    Returns:
        Summary of loaded skills
    """
    if not CHROMA_AVAILABLE or not semantic_mem:
        return "ChromaDB not available. Cannot load skills."

    from agent.core.skill_manager import get_skill_manager

    try:
        manager = get_skill_manager()
        activated_skills = manager.list_loaded_skills()

        if not activated_skills:
            return "No activated skills found."

        loaded = []
        failed = []

        for skill_name in activated_skills:
            result = await load_skill(skill_name)
            if result.startswith("✅"):
                loaded.append(skill_name)
            else:
                failed.append(skill_name)

        summary = f"**Loaded {len(loaded)} skills:**\n"
        for skill in loaded:
            summary += f"- {skill}\n"

        if failed:
            summary += f"\n**Failed:** {', '.join(failed)}"

        return summary
    except Exception as e:
        return f"Failed to load activated skills: {e}"
