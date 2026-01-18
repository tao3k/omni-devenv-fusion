# agent/core/vector_store/bootstrap.py
"""
Bootstrap operations for vector store.

Provides auto-ingestion for common project knowledge.
"""

from __future__ import annotations

from typing import Any

from .connection import get_vector_memory, _get_logger


async def bootstrap_knowledge_base() -> None:
    """
    Bootstrap the knowledge base with essential project documentation.

    Should be called on first run to populate with:
    - Git workflow rules
    - Coding standards
    - Architecture decisions
    - Preloaded skill definitions (SKILL.md)
    """
    # Default knowledge to ingest
    bootstrap_docs = [
        {
            "id": "git-workflow-001",
            "content": """
            Git Workflow Protocol:
            - All commits MUST use git_commit tool
            - Direct git commit is PROHIBITED
            - Commit message must follow conventional commits format
            - Authorization Protocol: Show analysis → Wait "yes" → Execute
            """,
            "metadata": {"domain": "git", "priority": "high"},
        },
        {
            "id": "tri-mcp-001",
            "content": """
            Tri-MCP Architecture:
            - orchestrator (The Brain): Planning, routing, reviewing
            - executor (The Hands): Git, testing, shell operations
            - coder (File Operations): Read/Write/Search files

            Each MCP server has a specific role and tools.
            """,
            "metadata": {"domain": "architecture", "priority": "high"},
        },
        {
            "id": "coding-standards-001",
            "content": """
            Coding Standards:
            - Follow agent/standards/lang-*.md for language-specific rules
            - Use Pydantic for type validation
            - Use structlog for logging
            - Write docstrings for all public functions
            """,
            "metadata": {"domain": "standards", "priority": "medium"},
        },
    ]

    vm = get_vector_memory()

    for doc in bootstrap_docs:
        await vm.add(
            documents=[doc["content"].strip()], ids=[doc["id"]], metadatas=[doc["metadata"]]
        )

    # Also ingest preloaded skill definitions (SKILL.md)
    await ingest_preloaded_skill_definitions()

    _get_logger().info("Knowledge base bootstrapped", docs=len(bootstrap_docs))


async def ingest_preloaded_skill_definitions() -> None:
    """
    Ingest SKILL.md (definition file) from all preloaded skills into the knowledge base.

    This ensures that when Claude processes user requests, it has access to
    the skill rules even if not explicitly loading the skill.

    The following skills are preloaded and their definitions will be ingested:
    - git: Commit authorization protocol
    - knowledge: Project rules and scopes
    - writer: Writing quality standards
    - filesystem: Safe file operations
    - terminal: Command execution rules
    - testing_protocol: Testing workflow
    """
    from agent.core.skill_registry import get_skill_registry
    from common.skills_path import SKILLS_DIR

    registry = get_skill_registry()
    preload_skills = registry.get_preload_skills()

    if not preload_skills:
        _get_logger().info("No preload skills configured")
        return

    vm = get_vector_memory()
    skills_ingested = 0

    for skill_name in preload_skills:
        definition_path = SKILLS_DIR.definition_file(skill_name)

        if not definition_path.exists():
            _get_logger().debug(f"Skill {skill_name} has no definition file")
            continue

        try:
            content = definition_path.read_text(encoding="utf-8")

            # Ingest with skill name as domain for filtering
            success = await vm.add(
                documents=[content],
                ids=[f"skill-{skill_name}-definition"],
                metadatas=[
                    {
                        "domain": "skill",
                        "skill": skill_name,
                        "priority": "high",
                        "source_file": str(definition_path),
                    }
                ],
            )

            if success:
                skills_ingested += 1
                _get_logger().info(f"Ingested definition for skill: {skill_name}")

        except Exception as e:
            _get_logger().error(f"Failed to ingest definition for skill {skill_name}: {e}")

    _get_logger().info(
        f"Preloaded skill definitions ingested: {skills_ingested}/{len(preload_skills)}"
    )
