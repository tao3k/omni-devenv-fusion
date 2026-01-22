"""
memory/scripts/memory.py - Memory Skill Commands

Modernized:
- @skill_command with autowire=True for clean dependency injection
- Uses PRJ_DATA_HOME/memory for persistent storage (not PRJ_CACHE)
- Uses ConfigPaths for semantic path resolution
- Refactored to use omni.foundation for embedding and vector_store.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger
from omni.foundation.services.embedding import get_embedding_service
from omni.foundation.services.vector import get_vector_store

logger = get_logger("skill.memory")

# =============================================================================
# Vector Store Initialization (Foundation Layer)
# =============================================================================


def _get_memory_path() -> Path:
    """Get memory root path using PRJ_DATA_HOME."""
    # Use ConfigPaths for semantic path resolution (Layer 1)
    paths = ConfigPaths()
    # Memory data goes in $PRJ_DATA_HOME/memory (persistent data, not cache)
    return paths.get_data_dir("memory")


MEMORY_ROOT = _get_memory_path()
DEFAULT_TABLE = "knowledge_base"


def _get_embedding(text: str) -> List[float]:
    """
    Get embedding using Foundation embedding service.

    Falls back to deterministic dummy embedding if service fails.
    """
    try:
        service = get_embedding_service()
        return service.embed(text)[0]
    except Exception as e:
        logger.warning(f"Embedding service failed, using fallback: {e}")
        # Fallback to deterministic hash-based embedding
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = [float(b) / 255.0 for b in hash_bytes]
        dimension = 1536  # Default fallback dimension
        repeats = (dimension + len(vector) - 1) // len(vector)
        return (vector * repeats)[:dimension]


def _load_skill_manifest(skill_name: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Load a skill's manifest and prompts."""
    from omni.foundation.config import get_setting

    paths = ConfigPaths()
    project_root = paths.project_root

    skills_path = get_setting("skills.path", "assets/skills")
    skills_dir = project_root / skills_path
    skill_path = skills_dir / skill_name

    if not skill_path.exists():
        return None, None

    # Load manifest from SKILL.md
    skill_md = skill_path / "SKILL.md"
    prompts = None

    manifest = None
    if skill_md.exists():
        try:
            import yaml

            content = skill_md.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 3)
                if len(parts) >= 2:
                    manifest = yaml.safe_load(parts[1])
        except Exception:
            pass

    # Load prompts.md
    prompts_path = skill_path / "prompts.md"
    if prompts_path.exists():
        prompts = prompts_path.read_text(encoding="utf-8")

    return manifest, prompts


# =============================================================================
# Memory Commands
# =============================================================================


@skill_command(
    name="save_memory",
    category="write",
    description="Store a key insight into long-term memory.",
    autowire=True,
)
async def save_memory(
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    paths: ConfigPaths | None = None,
) -> str:
    """
    [Long-term Memory] Store a key insight, decision, or learning into LanceDB.

    Use this when you've learned something reusable:
    - "Use scope 'nix' for flake changes"
    - "The project uses Conventional Commits"
    - "Always run 'just validate' before committing"

    Args:
        content: The insight to store (what you learned)
        metadata: Optional metadata dict (tags, domain, etc.)

    Returns:
        Confirmation message with stored content preview
    """
    client = get_vector_store()
    store = client.store
    if not store:
        return "VectorStore not available. Cannot store memory."

    try:
        doc_id = str(uuid.uuid4())

        # [FIX] Robust metadata handling - handle str, None, or dict
        if metadata is None:
            metadata = {}
        elif isinstance(metadata, str):
            try:
                # LLM sometimes passes JSON string instead of dict
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {"raw_metadata": metadata}
        elif not isinstance(metadata, dict):
            # Handle other unexpected types
            metadata = {"raw_metadata": str(metadata)}

        # Add timestamp to metadata (after ensuring it's a dict)
        metadata["timestamp"] = time.time()

        success = await client.add(content, metadata, collection=DEFAULT_TABLE)
        if success:
            return f"Saved memory [{doc_id[:8]}]: {content[:80]}..."
        return "Failed to store memory."
    except Exception as e:
        logger.error("save_memory failed", error=str(e))
        return f"Error saving memory: {str(e)}"


@skill_command(
    name="search_memory",
    category="read",
    description="Semantically search memory for relevant past experiences.",
    autowire=True,
)
async def search_memory(
    query: str,
    limit: int = 5,
    paths: ConfigPaths | None = None,
) -> str:
    """
    [Retrieval] Semantically search memory for relevant past experiences or rules.

    Examples:
    - search_memory("git commit message format")
    - search_memory("nixfmt error solution")
    - search_memory("how to add a new skill")

    Args:
        query: What you're looking for
        limit: Number of results to return (default: 5)

    Returns:
        Relevant memories found, or "No relevant memories found"
    """
    try:
        results = await get_vector_store().search(query, n_results=limit, collection=DEFAULT_TABLE)

        if not results:
            return "No matching memories found."

        output = [f"Found {len(results)} matches for '{query}':"]
        for r in results:
            # Format output for LLM consumption
            output.append(f"- [Score: {r.distance:.4f}] {r.content[:100]}")
            if r.metadata:
                output[-1] += f" (Meta: {json.dumps(r.metadata)[:50]}...)"

        return "\n".join(output)
    except Exception as e:
        logger.error("search_memory failed", error=str(e))
        return f"Error searching memory: {str(e)}"


@skill_command(
    name="index_memory",
    category="write",
    description="Optimize memory index for faster search (IVF-FLAT).",
    autowire=True,
)
async def index_memory(
    paths: ConfigPaths | None = None,
) -> str:
    """
    [Optimization] Create/optimize vector index for faster search.

    Call this after bulk imports to improve search performance.
    Uses IVF-FLAT algorithm for ANN search.

    Returns:
        Confirmation of index creation
    """
    try:
        success = await get_vector_store().create_index(collection=DEFAULT_TABLE)
        if success:
            return "Index creation/optimization complete. Search performance improved."
        return "Failed to create index."
    except Exception as e:
        return f"Error creating index: {str(e)}"


@skill_command(
    name="get_memory_stats",
    category="view",
    description="Get statistics about stored memories.",
    autowire=True,
)
async def get_memory_stats(
    paths: ConfigPaths | None = None,
) -> str:
    """
    [Diagnostics] Get statistics about stored memories.

    Returns:
        Count of stored memories
    """
    try:
        count = await get_vector_store().count(collection=DEFAULT_TABLE)
        return f"Stored memories: {count}"
    except Exception as e:
        return f"Error getting stats: {str(e)}"


@skill_command(
    name="load_skill",
    category="write",
    description="Load a skill's manifest into semantic memory.",
    autowire=True,
)
async def load_skill(
    skill_name: str,
    paths: ConfigPaths | None = None,
) -> str:
    """
    [Skill Loader] Load a single skill's manifest into semantic memory.

    Usage:
    - load_skill("git") - Load git skill
    - load_skill("terminal") - Load terminal skill

    This enables LLM to recall skill capabilities via semantic search.

    Returns:
        Confirmation message with skill details
    """
    client = get_vector_store()
    store = client.store
    if not store:
        return "VectorStore not available. Cannot load skill."

    manifest, prompts = _load_skill_manifest(skill_name)
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
    if prompts:
        document += f"\n---\n\n## System Prompts\n{prompts[:2000]}"

    doc_id = f"skill_{skill_name}"

    try:
        success = await client.add(
            document,
            metadata={
                "type": "skill_manifest",
                "skill_name": skill_name,
                "version": manifest.get("version", "unknown"),
            },
            collection=DEFAULT_TABLE,
        )
        if success:
            return f"Skill '{skill_name}' loaded into semantic memory."
        return f"Failed to load skill '{skill_name}'."
    except Exception as e:
        return f"Failed to load skill '{skill_name}': {e}"


__all__ = [
    "save_memory",
    "search_memory",
    "index_memory",
    "get_memory_stats",
    "load_skill",
    "MEMORY_ROOT",
    "DEFAULT_TABLE",
]
