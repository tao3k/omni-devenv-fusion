"""
src/agent/core/skill_discovery/indexing.py
Phase 36: Skill Index Management
Phase 37: Cognitive Indexing & Adaptive Routing

Functions for indexing skills into the vector store:
- reindex_skills_from_manifests: Full reindex
- index_single_skill: Incremental index (Phase 36.5)
- remove_skill_from_index: Remove from index (Phase 36.5)
- _generate_synthetic_queries: HyDE-style query generation (Phase 37.1)
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from .local import SkillDiscovery

logger = structlog.get_logger(__name__)

# ChromaDB collection name for skill registry
SKILL_REGISTRY_COLLECTION = "skill_registry"


def _extract_json_array(content: str) -> list[str] | None:
    """
    Extract JSON array from LLM response with multiple fallback strategies.

    Args:
        content: Raw LLM response content

    Returns:
        List of strings if found, None otherwise
    """
    import re

    content = content.strip()

    # Strategy 1: Handle markdown code blocks
    if "```" in content:
        # Extract content between code blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if match:
            content = match.group(1).strip()

    # Strategy 2: Direct JSON parse
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return [q for q in data if isinstance(q, str) and len(q) > 3]
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find JSON array in text
    match = re.search(r"\[[\s\S]*?\]", content)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [q for q in data if isinstance(q, str) and len(q) > 3]
        except json.JSONDecodeError:
            pass

    # Strategy 4: Extract quoted strings manually (fallback)
    quoted = re.findall(r'"([^"]{4,})"', content)
    if quoted:
        return quoted[:10]

    return None


async def _generate_synthetic_queries(manifest: Any) -> list[str]:
    """
    [Phase 37.1] Generate hypothetical user queries using LLM (HyDE-style).

    Uses the InferenceClient to predict how a user might naturally ask
    for this skill. This bridges the "description-query gap" that causes
    low recall in pure semantic search.

    Args:
        manifest: Skill manifest with name, description, and keywords

    Returns:
        List of synthetic user queries for indexing
    """
    # Lazy import to avoid slow module loading
    from common.mcp_core.inference import InferenceClient

    client = InferenceClient()

    # Build a concise prompt for query generation
    keywords = ", ".join(manifest.routing_keywords) if manifest.routing_keywords else "None"
    prompt = f"""Generate 10 diverse user queries for this skill.

Skill: {manifest.name}
Description: {manifest.description}
Keywords: {keywords}

Output: JSON array of query strings only.
Example: ["analyze code", "check my code", "review this file"]

JSON array:"""

    try:
        result = await client.complete(
            system_prompt="Output only valid JSON arrays. No explanation.",
            user_query=prompt,
            max_tokens=400,
        )

        if not result.get("success"):
            # Non-critical: skill will still be indexed without synthetic queries
            logger.debug(
                f"Synthetic query generation skipped for {manifest.name}",
                reason=result.get("error", "unknown"),
            )
            return []

        content = result.get("content", "")
        if not content:
            return []

        # Use robust extraction with fallbacks
        queries = _extract_json_array(content)
        if queries:
            valid = queries[:10]
            logger.debug(f"Generated {len(valid)} synthetic queries for {manifest.name}")
            return valid

        # Not an error - some LLM responses may not be parseable
        logger.debug(f"Could not parse synthetic queries for {manifest.name}")
        return []

    except Exception as e:
        # Log at debug level - synthetic queries are optional enhancement
        logger.debug(f"Synthetic query generation failed for {manifest.name}", error=str(e))
        return []


def _build_skill_document(manifest: Any, synthetic_queries: list[str] = None) -> str:
    """
    Build a rich semantic document from a skill manifest.

    Creates a comprehensive document that captures:
    - What the skill does (description)
    - How to use it (keywords and examples)
    - What tasks it helps with (use cases)
    - Related concepts and synonyms
    - [Phase 37.1] Synthetic user queries for HyDE-style indexing

    This rich document produces better embeddings for semantic search.

    Args:
        manifest: Skill manifest
        synthetic_queries: Optional list of LLM-generated user queries
    """
    if synthetic_queries is None:
        synthetic_queries = []

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

    # [Phase 37.1] Add synthetic user queries for HyDE-style indexing
    # These represent how users might naturally ask for this skill
    if synthetic_queries:
        parts.append(f"## User Query Examples: {', '.join(synthetic_queries)}")

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
    generate_synthetic: bool = True,
) -> dict[str, Any]:
    """
    Reindex all installed skills into the vector store.

    Scans SKILL.md files from all installed skills and creates
    semantic embeddings for intelligent discovery.

    Phase 37.1: Optionally generates synthetic user queries (HyDE-style)
    to improve recall for natural language queries.

    Args:
        clear_existing: Clear existing index before reindexing
        generate_synthetic: Generate synthetic queries using LLM (default: True)

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

            # [Phase 37.1] Generate synthetic queries if enabled
            synthetic_queries: list[str] = []
            if generate_synthetic:
                synthetic_queries = await _generate_synthetic_queries(manifest)

            # Build rich semantic document from manifest (with synthetic queries)
            semantic_text = _build_skill_document(manifest, synthetic_queries)

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
                        "synthetic_queries": len(synthetic_queries),  # Track for debugging
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


async def index_single_skill(
    skill_name: str, generate_synthetic: bool = True
) -> bool:
    """
    Phase 36.5: Index a single skill into the vector store.

    This is used for incremental updates when a skill is loaded
    or reloaded, ensuring the vector index stays in sync.

    Phase 36.6: Uses atomic upsert instead of delete+add to prevent race conditions.
    Phase 37.1: Optionally generates synthetic user queries for HyDE-style indexing.

    Args:
        skill_name: Name of the skill to index
        generate_synthetic: Generate synthetic queries using LLM (default: True)

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

        # [Phase 37.1] Generate synthetic queries if enabled
        synthetic_queries: list[str] = []
        if generate_synthetic:
            synthetic_queries = await _generate_synthetic_queries(manifest)

        # Build semantic document (with synthetic queries)
        semantic_text = _build_skill_document(manifest, synthetic_queries)

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
                        "synthetic_queries": len(synthetic_queries),
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
                        "synthetic_queries": len(synthetic_queries),
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
