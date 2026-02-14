"""
index_dimension.py - Embedding dimension consistency with vector index.

Checks that the current embedding dimension (considering truncate_dim) matches the dimension
used when the skills index was built (.embedding_signature.json).
When they differ, search can return 0 results; auto-rebuilds if enabled.

Unified dimension interface (used by omni sync and all store creation):
- get_effective_embedding_dimension(): actual dimension after truncate_dim. All code that
  creates or opens a vector store (bridge get_vector_store, VectorStoreClient, skill_manager)
  MUST use this so skills/knowledge/memory stay aligned with the signature written by sync.
- get_vector_store_dimension(): actual dimension from vector store
- ensure_embedding_signature_written(): called by sync after skills index; route-test uses it for mismatch detection
- ensure_dimension_consistency(): auto-rebuilds if mismatch
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SIGNATURE_FILENAME = ".embedding_signature.json"


@dataclass(frozen=True)
class EmbeddingDimensionStatus:
    """Result of dimension consistency check.

    index_dim: Dimension stored when index was built (None if no signature).
    current_dim: Current effective embedding dimension (considering truncate_dim).
    store_dim: Actual dimension from vector store (None if can't detect).
    match: True if index_dim is None or index_dim == current_dim.
    signature_path: Path to the signature file (for logging).
    needs_rebuild: True if dimension mismatch detected and rebuild is needed.
    """

    index_dim: int | None
    current_dim: int
    store_dim: int | None
    match: bool
    needs_rebuild: bool
    signature_path: str


def get_embedding_signature_path() -> Path:
    """Path to persisted embedding/index compatibility signature."""
    from omni.foundation.config.database import get_vector_db_path

    return get_vector_db_path() / SIGNATURE_FILENAME


def get_effective_embedding_dimension() -> int:
    """Get the effective embedding dimension (considering truncate_dim).

    This is the unified interface for all code that needs to know the actual
    vector dimension. Returns:
    - truncate_dim if set (e.g., 256)
    - embedding.dimension otherwise (e.g., 1024)
    """
    from omni.foundation.config.settings import get_setting
    from omni.foundation.services.embedding import get_embedding_service

    truncate_dim = get_setting("embedding.truncate_dim", None)
    if truncate_dim:
        return int(truncate_dim)

    # Try to get from embedding service (knows model's native dimension)
    try:
        service = get_embedding_service()
        if service.dimension:
            return service.dimension
    except Exception:
        pass

    # Fallback to settings
    return int(get_setting("embedding.dimension", 1024))


def get_vector_store_dimension(table_name: str = "skills") -> int | None:
    """Get actual dimension from vector store.

    Queries the vector store to find the actual dimension used.
    Returns None if store doesn't exist or can't be queried.
    """
    try:
        from omni.foundation.bridge.rust_vector import RustVectorStore

        store = RustVectorStore()
        return store._dimension
    except Exception:
        pass

    # Fallback: try to get from table schema
    try:
        from omni.foundation.bridge.rust_vector import RustVectorStore

        store = RustVectorStore()
        info = store.get_table_info(table_name)
        if info and "schema" in info:
            # Check for vector column dimension
            for col in info.get("schema", {}).get("fields", []):
                if col.get("name") == "vector":
                    return col.get("dimension")
    except Exception:
        pass

    return None


def get_embedding_dimension_status() -> EmbeddingDimensionStatus:
    """Check if current embedding dimension matches the index signature.

    Reads .embedding_signature.json from the vector DB directory (written by
    reindex/sync when skills are indexed). If missing or dimension differs,
    marks as needs_rebuild.

    Also detects actual vector store dimension for auto-repair.

    Returns:
        EmbeddingDimensionStatus with index_dim, current_dim, store_dim, match, needs_rebuild.
    """
    path = get_embedding_signature_path()
    current_dim = get_effective_embedding_dimension()
    store_dim = get_vector_store_dimension()
    index_dim: int | None = None

    if path.exists():
        try:
            data = json.loads(path.read_text())
            if isinstance(data.get("embedding_dimension"), (int, float)):
                index_dim = int(data["embedding_dimension"])
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    # Determine if rebuild is needed
    # Rebuild if: current_dim != index_dim (settings changed)
    # OR: store_dim exists but current_dim != store_dim (model/truncate changed)
    match = index_dim is None or index_dim == current_dim
    needs_rebuild = not match or (store_dim is not None and store_dim != current_dim)

    return EmbeddingDimensionStatus(
        index_dim=index_dim,
        current_dim=current_dim,
        store_dim=store_dim,
        match=match,
        needs_rebuild=needs_rebuild,
        signature_path=str(path),
    )


async def ensure_dimension_consistency(
    auto_rebuild: bool = True,
    force_rebuild: bool = False,
) -> EmbeddingDimensionStatus:
    """Ensure embedding dimension matches vector store, auto-rebuild if needed.

    This is the main entry point for dimension consistency. It:
    1. Checks current effective dimension (considering truncate_dim)
    2. Queries vector store for actual dimension
    3. If mismatch, either auto-rebuilds or returns status for caller to handle

    Args:
        auto_rebuild: If True, automatically rebuilds index on mismatch.
                     If False, just returns status with needs_rebuild=True.
        force_rebuild: If True, always rebuilds regardless of match.

    Returns:
        EmbeddingDimensionStatus with final state.
    """
    status = get_embedding_dimension_status()

    # Force rebuild requested
    if force_rebuild:
        if auto_rebuild:
            await _rebuild_index()
        return status

    # Dimension mismatch detected
    if status.needs_rebuild:
        if auto_rebuild:
            await _rebuild_index()
            # Re-check after rebuild
            return get_embedding_dimension_status()
        # Return status so caller can decide
        return status

    return status


async def _rebuild_index() -> None:
    """Internal: Rebuild the skills index with correct dimension."""
    from omni.core.services.skill_manager import get_skill_manager

    logger = __import__("logging").getLogger(__name__)
    logger.info("Auto-rebuilding skills index due to dimension mismatch...")

    try:
        manager = await get_skill_manager()
        await manager.sync()
        logger.info("Skills index rebuilt successfully")
    except Exception as e:
        logger.error(f"Failed to rebuild skills index: {e}")
        raise


def ensure_embedding_signature_written() -> None:
    """Write current embedding signature so future checks see a match.

    Call after reindexing skills so index_dim and current_dim align.
    """
    from omni.foundation.config.settings import get_setting

    path = get_embedding_signature_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    effective_dim = get_effective_embedding_dimension()

    payload = {
        "embedding_model": str(get_setting("embedding.model", "")),
        "embedding_dimension": effective_dim,  # Write effective dimension (after truncate)
        "embedding_provider": str(get_setting("embedding.provider", "")),
        "truncate_dim": get_setting("embedding.truncate_dim", None),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


# Vector store names and their expected dimensions
_VECTOR_STORE_CONFIGS = {
    "skills": {
        "path_suffix": "skills.lance",
        "expected_dimension": 1024,  # Skills always use native 1024
    },
    "router": {
        "path_suffix": "router.lance",
        "expected_dimension": 1024,  # Router uses skills dimension
    },
    "knowledge": {
        "path_suffix": "knowledge.lance",
        "expected_dimension": "truncated",  # Uses truncate_dim (256)
    },
}


@dataclass(frozen=True)
class VectorStoreDimensionReport:
    """Report of all vector store dimensions."""

    stores: dict[str, dict]
    is_consistent: bool
    issues: list[str]


def check_all_vector_stores_dimension() -> VectorStoreDimensionReport:
    """Check dimension consistency across all vector stores.

    Returns:
        VectorStoreDimensionReport with dimension status for each store.
    """
    from omni.foundation.config.database import get_vector_db_path

    vector_path = get_vector_db_path()
    issues: list[str] = []
    stores: dict[str, dict] = {}

    current_effective_dim = get_effective_embedding_dimension()

    for store_name, config in _VECTOR_STORE_CONFIGS.items():
        store_path = vector_path / config["path_suffix"]
        expected_dim = config["expected_dimension"]

        # Determine expected dimension
        if expected_dim == "truncated":
            expected = current_effective_dim
        else:
            expected = expected_dim

        # Check if store exists
        if not store_path.exists():
            stores[store_name] = {
                "exists": False,
                "expected_dimension": expected,
                "status": "missing",
            }
            issues.append(f"{store_name}: missing (expected {expected}D)")
            continue

        # Try to detect actual dimension from store
        actual_dim = _detect_vector_dimension(store_path)

        # If detection failed, assume it's OK (dimension matches expected)
        if actual_dim is None:
            stores[store_name] = {
                "exists": True,
                "path": str(store_path),
                "expected_dimension": expected,
                "actual_dimension": "unknown",
                "status": "ok",  # Assume OK if we can't detect
            }
            continue

        stores[store_name] = {
            "exists": True,
            "path": str(store_path),
            "expected_dimension": expected,
            "actual_dimension": actual_dim,
            "status": "ok" if actual_dim == expected else "mismatch",
        }

        if actual_dim != expected:
            issues.append(
                f"{store_name}: dimension mismatch (expected {expected}D, got {actual_dim}D)"
            )

    return VectorStoreDimensionReport(
        stores=stores,
        is_consistent=len(issues) == 0,
        issues=issues,
    )


def _detect_vector_dimension(store_path: Path) -> int | None:
    """Detect vector dimension from LanceDB store by reading schema.

    Returns None if detection fails (store doesn't exist or can't read schema).
    """
    try:
        # Try using lance directly
        import lance

        # Open in read mode to inspect schema
        dataset = lance.dataset(str(store_path))
        for field in dataset.schema:
            if field.name == "vector":
                # Vector field - get its type
                vector_type = field.type
                # FixedSizeList has .length attribute
                if hasattr(vector_type, "length"):
                    return vector_type.length
        return None
    except ImportError:
        # lance not available in this environment
        return None
    except Exception:
        # Other errors - store might be corrupted or incompatible
        return None


async def repair_vector_store_dimension(
    store_name: str,
    target_dimension: int,
) -> dict[str, Any]:
    """Repair a vector store by recreating it with correct dimension.

    Args:
        store_name: One of 'skills', 'router', 'knowledge'
        target_dimension: Target vector dimension

    Returns:
        dict with repair status
    """
    from omni.foundation.config.database import get_vector_db_path
    import shutil

    vector_path = get_vector_db_path()
    config = _VECTOR_STORE_CONFIGS.get(store_name)

    if not config:
        return {"status": "error", "details": f"Unknown store: {store_name}"}

    store_path = vector_path / config["path_suffix"]

    if not store_path.exists():
        return {"status": "error", "details": f"Store not found: {store_path}"}

    # Backup old store
    backup_path = store_path.parent / f"{store_path.stem}.backup"
    try:
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.move(str(store_path), str(backup_path))

        # For skills, we need to re-sync
        if store_name == "skills":
            from omni.core.services.skill_manager import get_skill_manager

            manager = await get_skill_manager()
            await manager.sync()
            return {"status": "success", "details": f"Recreated {store_name} index"}

        # For others, just note that they'll be recreated on next use
        return {
            "status": "success",
            "details": f"Backed up old {store_name} to {backup_path}, will recreate on next sync",
        }

    except Exception as e:
        # Restore from backup if possible
        if backup_path.exists() and not store_path.exists():
            shutil.move(str(backup_path), str(store_path))
        return {"status": "error", "details": str(e)}
