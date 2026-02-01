"""
omni.core.skills.discovery - Skill Discovery Module

High-performance skill discovery using Rust + LanceDB.

Architecture:
    LanceDB (SSOT) -> Foundation (Reader) -> Core (Discovery) -> Kernel

    ┌─────────────────┐
    │    LanceDB      │  ← Single Source of Truth (Rust/LanceDB)
    │   (Vector DB)   │
    └────────┬────────┘
             │
             ▼ Reads (Memory Registry - O(1) lookup)
    ┌─────────────────┐
    │Memory Registry  │  ← HashMap[tool_name -> ToolRecord]
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │SkillDiscovery   │
    │Service          │
    └────────┬────────┘
             │
             ▼ Returns
    ┌─────────────────┐
    │   Kernel        │  ← Consumes ToolMatch with usage_template
    └─────────────────┘

Unified Search Flow:
    1. Query → LanceDB (semantic retrieval) + Keyword matching (fallback)
    2. Tool Names → Memory Registry lookup (O(1))
    3. Schema → Template Generation (@omni("tool", {...}))
    4. Return enriched ToolMatch objects
"""

import json
import os
import inspect
from typing import Any, Callable, get_type_hints

from omni.foundation.bridge.scanner import (
    DiscoveredSkillRules,
    PythonSkillScanner,
)
from omni.foundation.config.logging import get_logger
from pydantic import BaseModel

logger = get_logger("omni.core.discovery")


def _py_type_to_json_type(py_type: Any) -> dict:
    """Map Python types to concise JSON Schema for LLM Context."""
    if py_type == str:
        return {"type": "string"}
    if py_type == int:
        return {"type": "integer"}
    if py_type == bool:
        return {"type": "boolean"}
    if py_type == float:
        return {"type": "number"}
    if py_type == list:
        return {"type": "array"}
    if py_type == dict:
        return {"type": "object"}
    # Handle Optional/Union types roughly for context window efficiency
    return {"type": "string", "description": str(py_type)}


def generate_usage_template(
    tool_name: str, input_schema: dict | str | None, implementation: Callable | None = None
) -> str:
    """
    Generate a STRICT usage template aligned with JSON Schema.
    Args:
        tool_name: Full tool name (e.g., "git.commit")
        input_schema: JSON Schema dict or string for the tool's parameters
        implementation: (Kept for API compatibility, not used for docstrings)
    """
    schema = {}

    # 1. Parse schema
    if input_schema:
        if isinstance(input_schema, str):
            try:
                schema = json.loads(input_schema)
                if isinstance(schema, str):
                    schema = json.loads(schema)
            except (json.JSONDecodeError, TypeError):
                schema = {}
        else:
            schema = input_schema

    if not schema:
        return f'@omni("{tool_name}", {{"..."}})'

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    args = {}
    for prop_name, prop_meta in properties.items():
        if prop_name not in required:
            if len(args) > 5:
                continue
            placeholder = f"<{prop_name}?>"
        else:
            prop_type = prop_meta.get("type", "string")
            enum_values = prop_meta.get("enum")

            if enum_values:
                placeholder = (
                    enum_values[0] if isinstance(enum_values[0], str) else f"<{prop_name}>"
                )
            elif prop_type == "integer":
                placeholder = 0
            elif prop_type == "number":
                placeholder = 0.0
            elif prop_type == "boolean":
                placeholder = True
            elif prop_type == "array":
                placeholder = []
            elif prop_type == "object":
                placeholder = {}
            else:
                placeholder = f"<{prop_name}>"

        args[prop_name] = placeholder

    args_str = json.dumps(args, separators=(", ", ": "))
    return f'@omni("{tool_name}", {args_str})'


class DiscoveredSkill(BaseModel):
    """Represents a discovered skill with its metadata.

    Created from Foundation's DiscoveredSkillRules via from_index_entry().
    """

    name: str
    path: str
    metadata: dict[str, Any]
    has_extensions: bool = False

    @classmethod
    def from_index_entry(cls, entry: DiscoveredSkillRules) -> "DiscoveredSkill":
        """Create from Foundation DiscoveredSkillRules object.

        Args:
            entry: DiscoveredSkillRules from PythonSkillScanner.scan_directory()

        Returns:
            DiscoveredSkill instance
        """
        # Check for extensions directory
        has_ext = False
        if entry.skill_path:
            ext_path = os.path.join(entry.skill_path, "extensions")
            has_ext = os.path.isdir(ext_path)

        return cls(
            name=entry.skill_name,
            path=entry.skill_path,
            metadata=entry.metadata,
            has_extensions=has_ext,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str, path: str) -> "DiscoveredSkill":
        """Create from raw dictionary (for testing/fallback).

        Args:
            data: Dictionary with skill metadata
            name: Skill name
            path: Skill path

        Returns:
            DiscoveredSkill instance
        """
        has_ext = os.path.isdir(os.path.join(path, "extensions"))
        return cls(
            name=name,
            path=path,
            metadata=data,
            has_extensions=has_ext,
        )


class ToolMatch(BaseModel):
    """Represents a tool matching a search query."""

    name: str
    skill_name: str
    description: str
    score: float
    matched_intent: str
    usage_template: str = ""


class ToolRecord:
    """Represents a tool record from the Memory Registry."""

    def __init__(
        self,
        name: str,
        skill_name: str,
        description: str,
        category: str = "",
        input_schema: str = "{}",
        file_path: str = "",
    ):
        self.name = name
        self.skill_name = skill_name
        self.description = description
        self.category = category
        self.input_schema = input_schema
        self.file_path = file_path

    @classmethod
    def from_tool_dict(cls, tool: dict, skill_name: str) -> "ToolRecord":
        """Create from tool dictionary (from LanceDB)."""
        return cls(
            name=tool.get("name", ""),
            skill_name=skill_name,
            description=tool.get("description", ""),
            category=tool.get("category", ""),
            input_schema=tool.get("input_schema", "{}"),
            file_path=tool.get("file_path", ""),
        )


class SkillDiscoveryService:
    """
    Level 2: Skill Discovery Service.

    Coordinates skill discovery using Hybrid Search:
    1. Vector DB (Rust/LanceDB) for semantic retrieval
    2. Memory Registry (HashMap) for O(1) schema lookup
    3. Template generation for enriched @omni() calls

    Architecture:
        - Memory Registry: O(1) lookup for tool metadata + schema
        - Vector Store: Semantic search for candidate selection
        - Fallback: Keyword matching when Vector DB unavailable

    Usage:
        service = SkillDiscoveryService()
        skills = service.discover_all()  # Reads from LanceDB
        for skill in skills:
            print(f"Found: {skill.name}")

        # Search for tools (hybrid: vector + keyword)
        matches = service.search_tools(query="read file", limit=3)
    """

    # Category boost mapping for query patterns
    CATEGORY_BOOSTS: dict[tuple[str, ...], list[str]] = {
        ("code", "refactor", "function", "class", "variable", "import"): [
            "engineering",
            "code_tools",
            "development",
        ],
        ("file", "read", "write", "edit", "create", "delete"): [
            "filesystem",
            "file_tools",
        ],
        ("search", "find", "grep", "query"): ["search", "query_tools"],
        ("git", "commit", "branch", "merge", "push"): ["version_control", "git"],
        ("test", "unit", "integration", "coverage"): ["testing", "qa"],
        ("api", "http", "request", "rest", "endpoint"): ["api", "network"],
        ("database", "sql", "query", "table"): ["database", "data"],
        ("shell", "run", "execute", "command", "bash"): ["shell", "execution"],
    }

    def __init__(self):
        """Initialize the discovery service.

        Uses Unified LanceDB Architecture:
        - Primary: LanceDB (Single Source of Truth)
        """
        self._index: list[dict] | None = None
        # Memory Registry: tool_name -> ToolRecord (O(1) lookup)
        self._registry: dict[str, ToolRecord] = {}
        self._registry_loaded = False
        self._source: str = "lance"  # Track data source for testing

    @property
    def source(self) -> str:
        """Return the data source used by the discovery service.

        Returns:
            "lance" when using LanceDB, "memory" for fallback
        """
        return self._source

    def _load_registry(self) -> dict[str, ToolRecord]:
        """Load tools into Memory Registry.

        Reads from LanceDB (Single Source of Truth).

        Returns:
            Dictionary mapping tool_name -> ToolRecord
        """
        if self._registry_loaded:
            return self._registry

        self._registry = {}

        # Step 1: Try LanceDB (Primary Source)
        try:
            from omni.foundation.bridge.rust_vector import get_vector_store

            store = get_vector_store()
            import asyncio

            tools = asyncio.run(store.list_all_tools())

            if tools:
                for tool in tools:
                    # Use tool_name (from Rust scanner) or id as fallback
                    tool_name = tool.get("tool_name") or tool.get("id", "")
                    if tool_name:
                        self._registry[tool_name] = ToolRecord(
                            name=tool_name,
                            skill_name=tool.get("skill_name", ""),
                            description=tool.get("description", "")
                            or tool.get("content", "")[:200],
                            category=tool.get("category", ""),
                            input_schema=tool.get("input_schema", "{}"),
                            file_path=tool.get("file_path", ""),
                        )
                self._registry_loaded = True
                logger.debug(f"Loaded {len(self._registry)} tools from LanceDB")
                return self._registry
        except Exception as e:
            logger.error(f"Failed to load from LanceDB: {e}")
            return {}

    def get_tool_record(self, tool_name: str) -> ToolRecord | None:
        """Get a single tool record from the Registry (O(1))."""
        registry = self._load_registry()
        return registry.get(tool_name)

    @property
    def tool_count(self) -> int:
        """Get the number of tools in the registry."""
        self._load_registry()
        return len(self._registry)

    async def search_tools_async(
        self, query: str, limit: int = 10, threshold: float = 0.1
    ) -> list[ToolMatch]:
        """
        Search for tools matching the given intent/query.

        Uses Rust Weighted RRF for hybrid search (vector + keyword + field boosting).
        Returns skill.discover as fallback when no tools match.

        Args:
            query: Natural language intent (e.g., "read markdown files")
            limit: Maximum number of results to return
            threshold: Minimum score threshold (0.0-1.0)

        Returns:
            List of ToolMatch objects sorted by score
        """
        try:
            import re
            from omni.foundation.bridge.rust_vector import get_vector_store
            from omni.foundation.services.embedding import get_embedding_service

            store = get_vector_store()
            embed_service = get_embedding_service()

            # Clean query for keyword search (remove quotes and other Tantivy-problematic chars)
            # Keep original for embedding to preserve semantic meaning
            keyword_query = re.sub(r'["\'\[\](){}]', "", query).strip()

            # Generate query embedding (sync embed handles event loop internally)
            try:
                query_vector = embed_service.embed(query)
                if query_vector and isinstance(query_vector[0], list):
                    query_vector = query_vector[0]
                else:
                    # Fallback: use empty vector for keyword-only search
                    query_vector = []
            except Exception as embed_err:
                logger.warning(f"Embedding failed: {embed_err}, using keyword-only search")
                query_vector = []

            # Use Rust search_tools with Weighted RRF + Field Boosting
            # Use cleaned query for keyword rescue to avoid Tantivy parse errors
            results = await store.search_tools(
                table_name="skills",
                query_vector=query_vector,
                query_text=keyword_query,
                limit=limit * 2,
                threshold=threshold,
            )

            matches = []
            for r in results:
                # Results are dicts from Rust binding
                if not isinstance(r, dict):
                    continue

                score = r.get("score", 0.0)
                if score < threshold:
                    continue

                tool_name = r.get("name", "")
                tool_record = self.get_tool_record(tool_name)

                usage = generate_usage_template(
                    tool_name, tool_record.input_schema if tool_record else "{}"
                )

                match = ToolMatch(
                    name=tool_name,
                    skill_name=str(r.get("skill_name") or ""),
                    description=str(r.get("description") or ""),
                    score=score,
                    matched_intent=query,
                    usage_template=usage,
                )
                matches.append(match)

            # If no results, return skill.discover as fallback (Discovery First rule)
            if not matches:
                return [
                    ToolMatch(
                        name="skill.discover",
                        skill_name="skill",
                        description="Discover available skills and tools",
                        score=0.05,
                        matched_intent=query,
                        usage_template='@omni("skill.discover", {"query": "..."})',
                    )
                ]

            return matches[:limit]

        except Exception as e:
            logger.warning(f"Rust search failed, falling back to keyword matching: {e}")
            fallback_results = self._search_tools_fallback(query, limit, threshold)

            # If no fallback results, return skill.discover
            if not fallback_results:
                return [
                    ToolMatch(
                        name="skill.discover",
                        skill_name="skill",
                        description="Discover available skills and tools",
                        score=0.05,
                        matched_intent=query,
                        usage_template='@omni("skill.discover", {"query": "..."})',
                    )
                ]

            return fallback_results[:limit]

    def search_tools(self, query: str, limit: int = 10, threshold: float = 0.1) -> list[ToolMatch]:
        """Synchronous wrapper for search_tools.

        Use this method when calling from synchronous code (e.g., tests, CLI).

        Args:
            query: Natural language intent (e.g., "read markdown files")
            limit: Maximum number of results to return
            threshold: Minimum score threshold (0.0-1.0)

        Returns:
            List of ToolMatch objects sorted by score
        """
        import asyncio

        return asyncio.run(self.search_tools_async(query, limit, threshold))

    def _detect_query_intent(self, query_words: set[str]) -> tuple[str, ...] | None:
        """Detect query intent based on keywords to enable category boosting."""
        for intent_keywords, _categories in self.CATEGORY_BOOSTS.items():
            if any(word in query_words for word in intent_keywords):
                return intent_keywords
        return None

    def _search_tools_fallback(self, query: str, limit: int, threshold: float) -> list[ToolMatch]:
        """Fallback keyword-based search when Rust search is unavailable."""
        registry = self._load_registry()
        query_lower = query.lower()
        query_words = set(query_lower.split())
        query_intent = self._detect_query_intent(query_words)

        matches: list[tuple[ToolMatch, float]] = []

        for tool_name, tool_record in registry.items():
            tool_score = 0.0
            tool_desc = tool_record.description
            tool_category = tool_record.category
            skill_name = tool_record.skill_name

            # Direct name match
            if query_lower.replace(" ", "_") in tool_name.lower():
                tool_score = max(tool_score, 0.95)
            elif query_lower.replace(" ", "") in tool_name.lower().replace("_", "").replace(
                ".", ""
            ):
                tool_score = max(tool_score, 0.85)

            # Category boost
            if query_intent and tool_category in self.CATEGORY_BOOSTS.get(query_intent, []):
                tool_score = max(tool_score, 0.8)

            # Token match in name
            for word in query_words:
                if word in tool_name.lower() and len(word) > 3:
                    tool_score = max(tool_score, 0.7)

            # Description match
            if query_lower in tool_desc.lower():
                tool_score = max(tool_score, 0.6)

            if tool_score >= threshold:
                usage = generate_usage_template(tool_name, tool_record.input_schema)
                match = ToolMatch(
                    name=tool_name,
                    skill_name=skill_name,
                    description=tool_desc,
                    score=tool_score,
                    matched_intent=query,
                    usage_template=usage,
                )
                matches.append((match, tool_score))

        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:limit]]

    def discover_all(self, locations: list[str] | None = None) -> list[DiscoveredSkill]:
        """Discover all skills from LanceDB.

        Args:
            locations: Ignored (kept for API compat).

        Returns:
            List of DiscoveredSkill objects sorted by name.
        """
        logger.debug("🔍 Accessing Skill Index from LanceDB...")

        # Use PythonSkillScanner to read from LanceDB
        scanner = PythonSkillScanner()
        index_entries = scanner.scan_directory()

        all_skills = []
        for entry in index_entries:
            skill = DiscoveredSkill.from_index_entry(entry)
            all_skills.append(skill)

        # Sort by name for consistent ordering
        all_skills.sort(key=lambda s: s.name)

        logger.info(f"📦 Index Service provided {len(all_skills)} skills from LanceDB")
        return all_skills

    def discover_one(self, skill_name: str) -> DiscoveredSkill | None:
        """Find a single skill in the Index by name.

        Args:
            skill_name: Name of the skill to find.

        Returns:
            DiscoveredSkill if found, None otherwise.
        """
        # This scans the in-memory list (fast enough for now)
        skills = self.discover_all()
        for skill in skills:
            if skill.name == skill_name:
                return skill
        return None

    def get_skills_with_extensions(self) -> list[DiscoveredSkill]:
        """Get all skills that have extensions directory."""
        skills = self.discover_all()
        return [s for s in skills if s.has_extensions]

    def get_analytics_dataframe(self):
        """Get all tools as a PyArrow Table for analytics.

        This method uses the Arrow-native export from Rust bindings
        for high-performance analytics operations.

        Returns:
            PyArrow Table with columns: id, content, skill_name, tool_name,
            file_path, keywords, etc. Returns None if analyzer unavailable.

        Note:
            Falls back to None when analyzer module is not available.
        """
        try:
            from omni.core.skills.analyzer import get_analytics_dataframe as _get_df

            return _get_df()
        except ImportError:
            # Analyzer module not available - return None
            return None

    def generate_system_context(self) -> str:
        """Generate system context using available data.

        This is optimized for generating tool context for LLM prompts.

        Returns:
            Formatted string with all tools in @omni() format
        """
        try:
            from omni.core.skills.analyzer import generate_system_context as _gen_ctx

            context = _gen_ctx()
            if context:  # Analyzer returned non-empty context
                return context
        except ImportError:
            pass

        # Fallback: generate from registry when analyzer is unavailable or returns empty
        registry = self._load_registry()
        if not registry:
            return ""

        context_parts = ["# Available Tools\n"]
        for tool_name, record in registry.items():
            usage = generate_usage_template(tool_name, record.input_schema)
            context_parts.append(f"- {usage}")

        return "\n".join(context_parts)

    def get_category_distribution(self) -> dict[str, int]:
        """Get tool count distribution by category.

        Returns:
            Dictionary mapping category names to tool counts
        """
        try:
            from omni.core.skills.analyzer import get_category_distribution as _get_dist

            return _get_dist()
        except ImportError:
            # Analyzer module not available - compute from registry
            registry = self._load_registry()
            distribution: dict[str, int] = {}
            for record in registry.values():
                category = record.category or "uncategorized"
                distribution[category] = distribution.get(category, 0) + 1
            return distribution


def is_rust_available() -> bool:
    """Check if Rust bindings are available.

    Note: In Rust-First Indexing, this returns True if the index
    was generated by the Rust scanner (which is always the case now).
    """
    return True


__all__ = [
    "DiscoveredSkill",
    "SkillDiscoveryService",
    "ToolMatch",
    "ToolRecord",
    "generate_usage_template",
    "is_rust_available",
]
