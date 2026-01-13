"""
src/agent/core/skill_discovery/indexing.py
Phase 36: Skill Index Management

Functions for indexing skills into the vector store:
- reindex_skills_from_manifests: Full reindex
- index_single_skill: Incremental index (Phase 36.5)
- remove_skill_from_index: Remove from index (Phase 36.5)
"""

from __future__ import annotations

from typing import Any

import structlog

from .local import SkillDiscovery

logger = structlog.get_logger(__name__)

# ChromaDB collection name for skill registry
SKILL_REGISTRY_COLLECTION = "skill_registry"


def _build_skill_document(manifest: Any) -> str:
    """
    Build a rich semantic document from a skill manifest.

    Creates a comprehensive document that captures:
    - What the skill does (description)
    - How to use it (keywords and examples)
    - What tasks it helps with (use cases)
    - Related concepts and synonyms

    This rich document produces better embeddings for semantic search.
    """
    parts = [
        f"## Skill: {manifest.name}",
        f"## Description: {manifest.description}",
    ]

    if manifest.routing_keywords:
        # Create a rich keyword section with examples
        keywords_str = ", ".join(manifest.routing_keywords)
        parts.append(f"## Keywords: {keywords_str}")

        # Expand keywords with usage examples
        examples = []
        for kw in manifest.routing_keywords[:10]:  # Limit to first 10
            # Add common verb + keyword patterns
            if " " not in kw:  # Single word keywords
                examples.append(f"how to {kw}")
                examples.append(f"{kw} task")
                examples.append(f"work with {kw}")
            else:  # Multi-word phrases
                examples.append(f"how to {kw}")
                examples.append(f"do {kw}")
        parts.append(f"## Usage Examples: {', '.join(examples)}")

    if manifest.intents:
        parts.append(f"## Intents: {', '.join(manifest.intents)}")

    # Add use case section based on keywords
    if manifest.routing_keywords:
        # Generate use case scenarios
        scenarios = []
        for kw in manifest.routing_keywords[:5]:
            scenarios.append(f"I need to {kw}")
            scenarios.append(f"Help me {kw}")
        parts.append(f"## Use Cases: {'; '.join(scenarios)}")

    # Add related concepts (common software development patterns)
    parts.append(f"## Category: Software Development Tool")

    return "\n".join(parts)


async def _index_remote_skills(vm: Any) -> int:
    """
    Index remote skills from known_skills.json into the vector store.

    Args:
        vm: VectorMemory instance

    Returns:
        Number of remote skills indexed
    """
    index = SkillDiscovery()._load_index()
    skills = index.get("skills", [])

    indexed = 0
    for skill in skills:
        try:
            skill_id = skill.get("id", "")
            if not skill_id:
                continue

            # Build rich semantic document (same format as local skills)
            keywords = skill.get("keywords", [])
            doc_parts = [
                f"## Skill: {skill.get('name', skill_id)}",
                f"## Description: {skill.get('description', '')}",
                f"## Keywords: {', '.join(keywords)}",
            ]

            # Add usage examples for remote skills too
            if keywords:
                examples = []
                for kw in keywords[:10]:
                    if " " not in kw:
                        examples.append(f"how to {kw}")
                        examples.append(f"{kw} task")
                    else:
                        examples.append(f"how to {kw}")
                doc_parts.append(f"## Usage Examples: {', '.join(examples)}")

            if skill.get("repository"):
                repo = skill.get("repository")
                doc_parts.append(f"## Repository: {repo.get('url', '')}")

            await vm.add(
                documents=["\n".join(doc_parts)],
                ids=[f"skill-remote-{skill_id}"],
                collection=SKILL_REGISTRY_COLLECTION,
                metadatas=[
                    {
                        "id": skill_id,
                        "name": skill.get("name", skill_id),
                        "keywords": ",".join(keywords),
                        "installed": "false",
                        "type": "remote",
                        "url": skill.get("url", ""),
                    }
                ],
            )
            indexed += 1

        except Exception as e:
            logger.warning(f"Failed to index remote skill {skill.get('id', '?')}", error=str(e))

    return indexed


async def reindex_skills_from_manifests(
    clear_existing: bool = True,
) -> dict[str, Any]:
    """
    Reindex all installed skills into the vector store.

    Scans SKILL.md files from all installed skills and creates
    semantic embeddings for intelligent discovery.

    Args:
        clear_existing: Clear existing index before reindexing

    Returns:
        Dict with stats about the reindexing operation
    """
    from agent.core.registry import get_skill_registry
    from agent.core.vector_store import get_vector_memory

    registry = get_skill_registry()
    vm = get_vector_memory()

    # Get all installed skills
    skills = registry.list_available_skills()
    indexed = 0
    errors = []

    # Clear existing index if requested
    if clear_existing:
        try:
            client = vm.client
            if client:
                # Get the collection and delete it
                try:
                    collection = client.get_collection(name="skill_registry")
                    collection.delete()
                    logger.info("Cleared existing skill registry collection")
                except Exception:
                    # Collection might not exist yet
                    pass
        except Exception as e:
            logger.warning("Failed to clear existing collection", error=str(e))

    # Index each skill
    for skill_name in skills:
        try:
            manifest = registry.get_skill_manifest(skill_name)
            if not manifest:
                continue

            # Build rich semantic document from manifest
            semantic_text = _build_skill_document(manifest)

            success = await vm.add(
                documents=[semantic_text],
                ids=[f"skill-{skill_name}"],
                collection=SKILL_REGISTRY_COLLECTION,
                metadatas=[
                    {
                        "id": skill_name,
                        "name": skill_name,
                        "keywords": ",".join(manifest.routing_keywords),
                        "installed": "true",
                        "type": "local",
                        "version": manifest.version,
                    }
                ],
            )

            if success:
                indexed += 1
                logger.debug(f"Indexed skill: {skill_name}")

        except Exception as e:
            errors.append({"skill": skill_name, "error": str(e)})
            logger.error(f"Failed to index skill {skill_name}", error=str(e))

    # Also index remote skills from known_skills.json
    remote_indexed = await _index_remote_skills(vm)

    result = {
        "local_skills_indexed": indexed,
        "remote_skills_indexed": remote_indexed,
        "total_skills_indexed": indexed + remote_indexed,
        "errors": errors,
    }

    logger.info("Skill reindex completed", **result)
    return result


async def index_single_skill(skill_name: str) -> bool:
    """
    Phase 36.5: Index a single skill into the vector store.

    This is used for incremental updates when a skill is loaded
    or reloaded, ensuring the vector index stays in sync.

    Phase 36.6: Uses atomic upsert instead of delete+add to prevent race conditions.

    Args:
        skill_name: Name of the skill to index

    Returns:
        True if indexed successfully, False otherwise
    """
    from agent.core.registry import get_skill_registry
    from agent.core.vector_store import get_vector_memory

    registry = get_skill_registry()
    vm = get_vector_memory()

    try:
        manifest = registry.get_skill_manifest(skill_name)
        if not manifest:
            logger.warning(f"Cannot index skill '{skill_name}': manifest not found")
            return False

        # Build semantic document
        semantic_text = _build_skill_document(manifest)

        # Phase 36.6: Use atomic upsert instead of delete+add
        # This prevents race conditions when multiple threads reload the same skill
        collection_name = SKILL_REGISTRY_COLLECTION
        skill_id = f"skill-{skill_name}"

        # Get the collection and use upsert (update or insert atomically)
        try:
            collection = vm.client.get_collection(name=collection_name)
            # ChromaDB's upsert is atomic and more efficient than delete+add
            collection.upsert(
                documents=[semantic_text],
                ids=[skill_id],
                metadatas=[
                    {
                        "id": skill_name,
                        "name": skill_name,
                        "keywords": ",".join(manifest.routing_keywords),
                        "installed": "true",
                        "type": "local",
                        "version": manifest.version,
                    }
                ],
            )
            logger.info(f"✅ [Index Sync] Upserted skill: {skill_name}")
            return True
        except Exception as e:
            # If upsert fails (e.g., collection doesn't exist), try to create and add
            logger.warning(f"Upsert failed for '{skill_name}', trying add: {e}")
            success = await vm.add(
                documents=[semantic_text],
                ids=[skill_id],
                collection=collection_name,
                metadatas=[
                    {
                        "id": skill_name,
                        "name": skill_name,
                        "keywords": ",".join(manifest.routing_keywords),
                        "installed": "true",
                        "type": "local",
                        "version": manifest.version,
                    }
                ],
            )
            if success:
                logger.info(f"✅ [Index Sync] Added skill: {skill_name}")
            return success

    except Exception as e:
        logger.error(f"Failed to index skill '{skill_name}'", error=str(e))
        return False


async def remove_skill_from_index(skill_name: str) -> bool:
    """
    Phase 36.5: Remove a skill from the vector store.

    This is called when a skill is unloaded to keep the index in sync.

    Args:
        skill_name: Name of the skill to remove

    Returns:
        True if removed successfully, False otherwise
    """
    from agent.core.vector_store import get_vector_memory

    try:
        vm = get_vector_memory()
        collection = vm.client.get_collection(name=SKILL_REGISTRY_COLLECTION)
        collection.delete(ids=[f"skill-{skill_name}"])
        logger.info(f"🗑️ [Index Sync] Removed skill from index: {skill_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to remove skill '{skill_name}' from index", error=str(e))
        return False


__all__ = [
    "reindex_skills_from_manifests",
    "index_single_skill",
    "remove_skill_from_index",
    "SKILL_REGISTRY_COLLECTION",
]
