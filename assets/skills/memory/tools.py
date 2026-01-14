"""
agent/skills/memory/tools.py
Phase 53: The Librarian - Long-term Memory Skill.

Role:
  Allows the Agent to semantically store and retrieve knowledge via LanceDB.
  Powered by Rust-based omni-vector (LanceDB wrapper).

Memory Path:
  {project_root}/.memory/lancedb/
"""

import json
import os
import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)

# =============================================================================
# Vector Store Initialization (Rust + LanceDB)
# =============================================================================


def _get_memory_path() -> Path:
    """Get memory root path."""
    from common.cache_path import CACHE_DIR
    from common.settings import get_setting

    # Check for custom override in settings.yaml
    custom_path = get_setting("memory.path", "")
    if custom_path:
        return Path(custom_path)

    return CACHE_DIR("memory")


MEMORY_ROOT = _get_memory_path()
DB_PATH = MEMORY_ROOT / "lancedb"
DB_PATH.mkdir(parents=True, exist_ok=True)

# Try to initialize Rust VectorStore
try:
    import omni_core_rs

    # Get embedding dimension from the embedding service
    # This ensures Rust LanceDB schema matches Python embedding dimension
    embedding_dimension = 384  # Default for BGE-small
    try:
        from agent.core.embedding import get_embedding_service

        embedding_dimension = get_embedding_service().dimension
        logger.info(f"Using embedding dimension: {embedding_dimension}")
    except Exception:
        logger.warning(f"Could not get embedding dimension, using default: {embedding_dimension}")

    _store = omni_core_rs.PyVectorStore(str(DB_PATH), embedding_dimension)
    RUST_AVAILABLE = True
    logger.info(
        f"Librarian (VectorStore) initialized at {DB_PATH} with dimension {embedding_dimension}"
    )
except Exception as e:
    RUST_AVAILABLE = False
    _store = None
    logger.warning(f"Failed to init Rust VectorStore: {e}")

# Default table name
DEFAULT_TABLE = "knowledge_base"


def _get_embedding(text: str) -> List[float]:
    """
    [Phase 53.5] Real Semantic Embedding using FastEmbed or OpenAI.

    Falls back to DummyEmbedding if real embedding service fails.
    """
    try:
        from agent.core.embedding import get_embedding_service

        service = get_embedding_service()
        return service.embed(text)[0]
    except Exception as e:
        logger.warning(f"Real embedding failed, using dummy: {e}")
        # Fallback to dummy embedding for testing
        seed = sum(ord(c) for c in text) % 100
        dimension = 384  # BGE-small default dimension
        return [0.001 * seed] * dimension


# =============================================================================
# Memory Commands
# =============================================================================


@skill_command(
    name="save_memory",
    category="write",
    description="Store a key insight into long-term memory.",
)
async def save_memory(content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
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
    if not RUST_AVAILABLE or not _store:
        return "Rust VectorStore not available. Cannot store memory."

    try:
        doc_id = str(uuid.uuid4())
        vector = _get_embedding(content)

        # Add timestamp to metadata
        if metadata is None:
            metadata = {}
        metadata["timestamp"] = time.time()

        _store.add_documents(DEFAULT_TABLE, [doc_id], [vector], [content], [json.dumps(metadata)])
        return f"Saved memory [{doc_id[:8]}]: {content[:80]}..."
    except Exception as e:
        logger.error("save_memory failed", error=str(e))
        return f"Error saving memory: {str(e)}"


@skill_command(
    name="search_memory",
    category="read",
    description="Semantically search memory for relevant past experiences.",
)
async def search_memory(query: str, limit: int = 5) -> str:
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
    if not RUST_AVAILABLE or not _store:
        return "Rust VectorStore not available. Cannot search memory."

    try:
        vector = _get_embedding(query)

        # Call Rust search - returns JSON strings
        results_json = _store.search(DEFAULT_TABLE, vector, limit)

        if not results_json:
            return "No matching memories found."

        output = [f"Found {len(results_json)} matches for '{query}':"]
        for r_str in results_json:
            r = json.loads(r_str)
            dist = r.get("distance", 0.0)
            content = r.get("content", "")
            meta = r.get("metadata", {})

            # Format output for LLM consumption
            output.append(f"- [Score: {dist:.4f}] {content[:100]}")
            if meta:
                output[-1] += f" (Meta: {json.dumps(meta)[:50]}...)"

        return "\n".join(output)
    except Exception as e:
        logger.error("search_memory failed", error=str(e))
        return f"Error searching memory: {str(e)}"


@skill_command(
    name="index_memory",
    category="write",
    description="Optimize memory index for faster search (IVF-FLAT).",
)
async def index_memory() -> str:
    """
    [Optimization] Create/optimize vector index for faster search.

    Call this after bulk imports to improve search performance.
    Uses IVF-FLAT algorithm for ANN search.

    Returns:
        Confirmation of index creation
    """
    if not RUST_AVAILABLE or not _store:
        return "Rust VectorStore not available. Cannot create index."

    try:
        _store.create_index(DEFAULT_TABLE)
        return "Index creation/optimization complete. Search performance improved."
    except Exception as e:
        return f"Error creating index: {str(e)}"


@skill_command(
    name="get_memory_stats",
    category="view",
    description="Get statistics about stored memories.",
)
async def get_memory_stats() -> str:
    """
    [Diagnostics] Get statistics about stored memories.

    Returns:
        Count of stored memories
    """
    if not RUST_AVAILABLE or not _store:
        return "Rust VectorStore not available."

    try:
        count = _store.count(DEFAULT_TABLE)
        return f"Stored memories: {count}"
    except Exception as e:
        return f"Error getting stats: {str(e)}"


@skill_command(
    name="load_skill",
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
    if not RUST_AVAILABLE or not _store:
        return "Rust VectorStore not available. Cannot load skill."

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
    vector = _get_embedding(document)

    try:
        _store.add_documents(
            DEFAULT_TABLE,
            [doc_id],
            [vector],
            [document],
            [
                json.dumps(
                    {
                        "type": "skill_manifest",
                        "skill_name": skill_name,
                        "version": manifest.get("version", "unknown"),
                    }
                )
            ],
        )

        return f"✅ Skill '{skill_name}' loaded into semantic memory."
    except Exception as e:
        return f"Failed to load skill '{skill_name}': {e}"


# =============================================================================
# Helper Functions
# =============================================================================


def _load_skill_manifest(skill_name: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Load a skill's manifest and prompts."""
    from common.settings import get_setting
    from common.gitops import get_project_root

    skills_path = get_setting("skills.path", "assets/skills")
    project_root = get_project_root()
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
