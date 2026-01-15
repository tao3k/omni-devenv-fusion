"""
memory/scripts/memory.py - Memory Skill Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from agent.skills.decorators import skill_script

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

# Lazy initialization for VectorStore (avoid re-initialization on repeated imports)
_cached_store: Optional[Any] = None
RUST_AVAILABLE = False


def _get_store() -> Optional[Any]:
    """Lazily initialize and return the VectorStore."""
    global _cached_store, RUST_AVAILABLE

    if _cached_store is not None:
        return _cached_store

    try:
        import omni_core_rs

        # Get embedding dimension from the embedding service
        # This ensures Rust LanceDB schema matches Python embedding dimension
        embedding_dimension = 384  # Default for BGE-small
        try:
            from agent.core.embedding import get_embedding_service

            embedding_dimension = get_embedding_service().dimension
        except Exception:
            pass  # Use default dimension

        _cached_store = omni_core_rs.PyVectorStore(str(DB_PATH), embedding_dimension)
        RUST_AVAILABLE = True
        # Only log on first initialization
        logger.debug(
            f"Librarian (VectorStore) ready at {DB_PATH} with dimension {embedding_dimension}"
        )
    except Exception as e:
        RUST_AVAILABLE = False
        _cached_store = None
        logger.warning(f"Failed to init Rust VectorStore: {e}")

    return _cached_store


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


# =============================================================================
# Memory Commands
# =============================================================================


@skill_script(
    name="save_memory",
    category="write",
    description="Store a key insight into long-term memory.",
    inject_settings=["memory.path"],
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
    store = _get_store()
    if not RUST_AVAILABLE or not store:
        return "Rust VectorStore not available. Cannot store memory."

    try:
        doc_id = str(uuid.uuid4())
        vector = _get_embedding(content)

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

        store.add_documents(DEFAULT_TABLE, [doc_id], [vector], [content], [json.dumps(metadata)])
        return f"Saved memory [{doc_id[:8]}]: {content[:80]}..."
    except Exception as e:
        logger.error("save_memory failed", error=str(e))
        return f"Error saving memory: {str(e)}"


@skill_script(
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
    store = _get_store()
    if not RUST_AVAILABLE or not store:
        return "Rust VectorStore not available. Cannot search memory."

    try:
        vector = _get_embedding(query)

        # Call Rust search - returns JSON strings
        results_json = store.search(DEFAULT_TABLE, vector, limit)

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


@skill_script(
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
    store = _get_store()
    if not RUST_AVAILABLE or not store:
        return "Rust VectorStore not available. Cannot create index."

    try:
        store.create_index(DEFAULT_TABLE)
        return "Index creation/optimization complete. Search performance improved."
    except Exception as e:
        return f"Error creating index: {str(e)}"


@skill_script(
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
    store = _get_store()
    if not RUST_AVAILABLE or not store:
        return "Rust VectorStore not available."

    try:
        count = store.count(DEFAULT_TABLE)
        return f"Stored memories: {count}"
    except Exception as e:
        return f"Error getting stats: {str(e)}"


@skill_script(
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
    store = _get_store()
    if not RUST_AVAILABLE or not store:
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

    store = _get_store()
    if not RUST_AVAILABLE or not store:
        return "Rust VectorStore not available. Cannot load skill."

    try:
        store.add_documents(
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
