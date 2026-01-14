"""
agent/core/skill_loader.py
Phase 60: The Grand Bazaar - Semantic Tool Routing & Dynamic Skill Loading

Dynamic tool loading system that:
1. Indexes all available skills into vector store
2. Retrieves relevant tools based on semantic task matching
3. Enables "skill marketplace" behavior for scalable agent

Philosophy:
- Context Window is limited: Don't load all 100+ tools at once
- Semantic Routing: Only load tools relevant to current task
- Lazy Loading: Tools are loaded on-demand, not at startup

Usage:
    from agent.core.skill_loader import get_skill_loader, load_tools_for_task

    # Index all skills (run once or after adding new skills)
    loader = get_skill_loader()
    loader.index_all_skills()

    # Get relevant tools for a task
    tools = load_tools_for_task("commit changes to git")
    # Returns: ToolRegistry with only git-related tools
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from dataclasses import dataclass, field

import structlog

from agent.skills.core.skill_manifest import SKILL_FILE

if TYPE_CHECKING:
    from agent.core.registry.core import ToolRegistry
    from agent.core.embedding import EmbeddingService

logger = structlog.get_logger(__name__)

# Collection name for skill indexing
SKILL_COLLECTION = "system_skills"

# Default number of tools to retrieve
DEFAULT_TOP_K = 5


@dataclass
class IndexedSkill:
    """A skill that has been indexed in the vector store."""

    name: str
    description: str
    routing_keywords: List[str]
    intents: List[str]
    module_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillLoader:
    """
    Skill Loader - Indexes and retrieves skills for semantic routing.

    Phase 60: The Grand Bazaar

    Features:
    - Scans assets/skills/ for all SKILL.md files
    - Extracts metadata (name, description, routing_keywords, intents)
    - Indexes into vector store for semantic search
    - Retrieves top-K relevant skills for a given task
    """

    _instance: Optional["SkillLoader"] = None
    _indexed: bool = False
    _skills: Dict[str, IndexedSkill] = {}

    def __new__(cls) -> "SkillLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._skills = {}

    def _find_skill_files(self, base_path: Optional[Path] = None) -> List[Path]:
        """Find all SKILL.md files in assets/skills/."""
        from common.gitops import get_project_root

        root = base_path or get_project_root()
        skills_dir = root / "assets" / "skills"

        if not skills_dir.exists():
            logger.warning("Skills directory not found", path=str(skills_dir))
            return []

        skill_files: List[Path] = []
        for item in skills_dir.rglob(f"*/{SKILL_FILE}"):
            if item.is_file():
                skill_files.append(item)

        logger.info("Found skill files", count=len(skill_files))
        return skill_files

    def _parse_skill_manifest(self, skill_file: Path) -> Optional[IndexedSkill]:
        """Parse a SKILL.md file and extract metadata."""
        try:
            content = skill_file.read_text()

            # Parse YAML frontmatter
            import yaml

            # Extract frontmatter between --- markers
            frontmatter_match = content.split("---")
            if len(frontmatter_match) < 2:
                logger.warning("No frontmatter found", file=str(skill_file))
                return None

            frontmatter_text = frontmatter_match[1]
            data = yaml.safe_load(frontmatter_text)

            if not data:
                logger.warning("Empty frontmatter", file=str(skill_file))
                return None

            # Use frontmatter description (not body text)
            description = data.get("description", "")

            # Get routing keywords
            routing_keywords = data.get("routing_keywords", [])

            # Get intents
            intents = data.get("intents", [])

            # Module path for importing
            skill_dir = skill_file.parent
            module_path = str(skill_dir.relative_to(skill_dir.anchor))

            skill = IndexedSkill(
                name=data.get("name", skill_dir.name),
                description=description or data.get("description", ""),
                routing_keywords=routing_keywords,
                intents=intents,
                module_path=module_path,
                metadata=data,
            )

            return skill

        except Exception as e:
            logger.error("Failed to parse skill", file=str(skill_file), error=str(e))
            return None

    def _get_skill_search_text(self, skill: IndexedSkill) -> str:
        """Generate search text for a skill (for embedding)."""
        parts = [
            f"Skill: {skill.name}",
            f"Description: {skill.description}",
        ]
        if skill.routing_keywords:
            parts.append(f"Keywords: {' '.join(skill.routing_keywords)}")
        if skill.intents:
            parts.append(f"Intents: {' '.join(skill.intents)}")
        return " | ".join(parts)

    async def index_all_skills(self, base_path: Optional[Path] = None) -> int:
        """
        Scan all skills and index them into vector store.

        Args:
            base_path: Optional base path (defaults to project root)

        Returns:
            Number of skills indexed
        """
        from agent.core.vector_store import get_vector_memory
        from agent.core.embedding import get_embedding_service

        logger.info("🔍 Indexing all skills into vector store...")

        skill_files = self._find_skill_files(base_path)
        if not skill_files:
            logger.warning("No skill files found to index")
            return 0

        # Parse all skills
        skills: List[IndexedSkill] = []
        for sf in skill_files:
            skill = self._parse_skill_manifest(sf)
            if skill:
                skills.append(skill)
                self._skills[skill.name] = skill

        if not skills:
            logger.warning("No valid skills found after parsing")
            return 0

        # Generate search texts and embeddings
        search_texts = [self._get_skill_search_text(s) for s in skills]
        ids = [s.name for s in skills]
        metadatas = [
            {
                "module_path": s.module_path,
                "description": s.description,
                "routing_keywords": json.dumps(s.routing_keywords),
                "intents": json.dumps(s.intents),
            }
            for s in skills
        ]

        # Embed all skill texts
        embed_service = get_embedding_service()
        vectors = embed_service.embed(search_texts)

        # Store in vector store
        vm = get_vector_memory()
        if vm.store:
            # Use vm.add directly (async method)
            success = await vm.add(
                documents=search_texts,
                ids=ids,
                collection=SKILL_COLLECTION,
                metadatas=metadatas,
            )
            if success:
                logger.info("✅ Skills indexed successfully", count=len(skills))
            else:
                logger.error("Failed to ingest skills into vector store")
        else:
            # Fallback: Store in memory only (for testing without vector store)
            logger.warning("Vector store not available, using in-memory fallback")
            self._skills = {s.name: s for s in skills}

        self._indexed = True
        return len(skills)

    async def retrieve_relevant_skills(
        self, task: str, top_k: int = DEFAULT_TOP_K
    ) -> List[IndexedSkill]:
        """
        Hybrid Semantic Router: Vector Search + Keyword Boosting.

        Scoring: 70% Vector Similarity + 30% Keyword Match
        If a skill matches keywords strongly, it can outrank higher vector scores.

        Args:
            task: The task description (e.g., "commit changes to git")
            top_k: Maximum number of skills to return

        Returns:
            List of indexed skills sorted by relevance
        """
        from agent.core.vector_store import get_vector_memory
        from agent.core.embedding import get_embedding_service

        logger.info("🔍 Searching for relevant skills (Hybrid Mode)", task=task[:50])

        # If not indexed yet, do it now
        if not self._indexed:
            logger.info("Skills not indexed yet, indexing now...")
            await self.index_all_skills()

        vm = get_vector_memory()
        task_lower = task.lower()

        # Combine vector search with keyword matching
        candidates: dict[str, float] = {}  # skill_name -> combined_score

        # Step 1: Vector Search (Base Score - 70% weight)
        # Get more candidates to allow keyword boosting to reorder
        search_limit = max(top_k * 3, 10)  # Get at least 10 candidates
        if vm.store:
            embed_service = get_embedding_service()
            embed_service.embed(task)  # Generate embedding

            results = await vm.search(query=task, n_results=search_limit, collection=SKILL_COLLECTION)

            for r in results:
                skill_name = r.id
                # Convert distance to similarity (smaller distance = higher score)
                vector_score = max(0.0, 1.0 - r.distance)
                # Weight: 70%
                candidates[skill_name] = vector_score * 0.7

            logger.debug(
                "Vector search completed",
                candidates_count=len(candidates),
                task=task[:50],
            )

        # Step 2: Keyword Boosting (30% weight)
        # Check all indexed skills for keyword matches
        for skill_name, skill in self._skills.items():
            keyword_score = self._calculate_keyword_score(task_lower, skill)

            if keyword_score > 0:
                # Weight: 30%
                keyword_contribution = keyword_score * 0.3

                if skill_name in candidates:
                    # Combine with existing vector score
                    candidates[skill_name] += keyword_contribution
                    logger.debug(
                        f"Boosted {skill_name} with keyword score",
                        vector_score=candidates[skill_name] - keyword_contribution,
                        final_score=candidates[skill_name],
                    )
                else:
                    # Pure keyword match "dark horse" - give base score
                    candidates[skill_name] = 0.3 + keyword_contribution
                    logger.debug(
                        f"Keyword-only match: {skill_name}",
                        score=candidates[skill_name],
                    )

        # Step 3: Sort by combined score and return top-k
        sorted_candidates = sorted(candidates.items(), key=lambda x: -x[1])
        top_skills = [
            self._skills[skill_name]
            for skill_name, score in sorted_candidates[:top_k]
            if skill_name in self._skills
        ]

        # Log selection results
        logger.info(
            "🎯 Router Selection",
            task=task[:50],
            selected=[f"{s.name}({candidates.get(s.name, 0):.2f})" for s in top_skills],
        )

        return top_skills

    def _calculate_keyword_score(self, task_lower: str, skill: IndexedSkill) -> float:
        """
        Calculate keyword match score for a skill.

        Scoring:
        - Exact keyword match in routing_keywords: 1.0 (full weight)
        - Partial match: 0.5
        - Intent match: 0.8
        """
        score = 0.0

        # Check routing_keywords (highest priority - exact match)
        for kw in skill.routing_keywords:
            kw_lower = kw.lower()
            if kw_lower in task_lower:
                # Check for word boundary match
                import re
                # Match whole word to avoid false positives like "git" in "digit"
                if re.search(rf'\b{re.escape(kw_lower)}\b', task_lower):
                    return 1.0  # Full score for exact keyword match
                elif kw_lower in task_lower:
                    score = max(score, 0.5)  # Partial match

        # Check intents
        for intent in skill.intents:
            if intent.lower() in task_lower:
                score = max(score, 0.8)  # High score for intent match

        # Check if description keywords are in task
        if skill.description.lower() in task_lower:
            score = max(score, 0.3)

        return score

    def _keyword_match(self, task: str, top_k: int = DEFAULT_TOP_K) -> List[IndexedSkill]:
        """Simple keyword matching as fallback."""
        task_lower = task.lower()
        scored: List[tuple[float, IndexedSkill]] = []

        for skill in self._skills.values():
            score = 0.0

            # Check description
            if skill.description.lower() in task_lower:
                score += 2.0

            # Check routing keywords
            for kw in skill.routing_keywords:
                if kw.lower() in task_lower:
                    score += 1.0

            # Check intents
            for intent in skill.intents:
                if intent.lower() in task_lower:
                    score += 1.5

            if score > 0:
                scored.append((score, skill))

        # Sort by score descending
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:top_k]]

    def get_skill_by_name(self, name: str) -> Optional[IndexedSkill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_all_skills(self) -> List[str]:
        """List all indexed skill names."""
        return list(self._skills.keys())

    def is_indexed(self) -> bool:
        """Check if skills have been indexed."""
        return self._indexed


def get_skill_loader() -> SkillLoader:
    """Get the global SkillLoader instance."""
    return SkillLoader()


async def load_tools_for_task(task: str, top_k: int = DEFAULT_TOP_K) -> "ToolRegistry":
    """
    Load tools relevant to the given task.

    This is the main entry point for dynamic tool loading.

    Args:
        task: Task description (e.g., "commit changes to git")
        top_k: Maximum number of tools to load

    Returns:
        ToolRegistry with only relevant tools registered
    """
    from agent.core.registry.core import ToolRegistry
    from agent.core.skill_loader import get_skill_loader

    loader = get_skill_loader()
    skills = await loader.retrieve_relevant_skills(task, top_k=top_k)

    logger.info(
        "Loaded tools for task",
        task=task[:50],
        skill_count=len(skills),
        skills=[s.name for s in skills],
    )

    registry = ToolRegistry()

    # Import and register tools from each skill
    for skill in skills:
        try:
            # Dynamic import the skill module
            module = _import_skill_module(skill.module_path)
            if module and hasattr(module, "get_tools"):
                tools = module.get_tools()
                for tool in tools:
                    registry.register(tool)
                    logger.debug(f"Registered tool: {tool.name}")
        except Exception as e:
            logger.error(
                "Failed to load skill tools",
                skill=skill.name,
                error=str(e),
            )

    return registry


def _import_skill_module(module_path: str) -> Optional[Any]:
    """Dynamically import a skill module."""
    try:
        # Convert path to module name
        # e.g., "/assets/skills/git" -> "agent.skills.git"
        parts = module_path.split(os.sep)
        if parts[0] == "":
            parts = parts[1:]

        # Handle different skill locations
        if parts[0] == "assets" and parts[1] == "skills":
            module_name = ".".join(["agent", "skills"] + parts[2:])
        else:
            module_name = ".".join(parts)

        import importlib

        return importlib.import_module(module_name)
    except ImportError as e:
        logger.warning("Could not import skill module", module=module_path, error=str(e))
        return None


async def index_system_skills() -> int:
    """
    Convenience function to index all system skills.

    Call this during startup or when new skills are added.

    Returns:
        Number of skills indexed
    """
    loader = get_skill_loader()
    return await loader.index_all_skills()


__all__ = [
    "SkillLoader",
    "IndexedSkill",
    "get_skill_loader",
    "load_tools_for_task",
    "index_system_skills",
    "SKILL_COLLECTION",
    "DEFAULT_TOP_K",
]
